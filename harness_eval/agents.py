"""Agent adapters. Each one runs the agent headless inside the workspace and
returns cost/usage telemetry. Adding an agent = adding one function here."""
from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import Harness, Task


@dataclass
class AgentResult:
    ok: bool
    exit_code: int | None
    duration_s: float
    cost_usd: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    num_turns: int | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def build_prompt(harness: Harness, task: Task) -> str:
    return f"{harness.prompt_prefix.strip()}\n\n{task.prompt}".strip()


def run_agent(harness: Harness, task: Task, ws: Path, log_dir: Path, trial: int) -> AgentResult:
    prompt = build_prompt(harness, task)
    (log_dir / "prompt.txt").write_text(prompt)
    runner = {
        "claude-code": _claude_code,
        "codex": _codex,
        "command": _command,
        "replay": _replay,
    }.get(harness.agent)
    if runner is None:
        raise SystemExit(f"Unknown agent '{harness.agent}' in harness {harness.name}")
    return runner(harness, task, ws, log_dir, trial, prompt)


def _exec(cmd: list[str], ws: Path, log_dir: Path, harness: Harness, timeout: int, prompt: str):
    env = {**os.environ, **harness.env, "HEV_PROMPT": prompt}
    start = time.monotonic()
    try:
        res = subprocess.run(cmd, cwd=ws, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired as e:
        (log_dir / "agent_stdout.txt").write_text((e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""))
        return None, time.monotonic() - start, f"timeout after {timeout}s"
    except FileNotFoundError:
        return None, time.monotonic() - start, f"agent binary not found: {cmd[0]}"
    (log_dir / "agent_stdout.txt").write_text(res.stdout)
    (log_dir / "agent_stderr.txt").write_text(res.stderr)
    return res, time.monotonic() - start, None


def _claude_code(harness, task, ws, log_dir, trial, prompt) -> AgentResult:
    cmd = ["claude", "-p", prompt, "--output-format", "json"]
    if harness.model:
        cmd += ["--model", harness.model]
    cmd += harness.extra_args
    res, dur, err = _exec(cmd, ws, log_dir, harness, task.timeout_s, prompt)
    if err:
        return AgentResult(False, None, dur, error=err)
    data = _last_json(res.stdout)
    usage = (data or {}).get("usage") or {}
    inp = sum(int(usage.get(k) or 0) for k in
              ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")) if usage else None
    return AgentResult(
        ok=res.returncode == 0 and not (data or {}).get("is_error", False),
        exit_code=res.returncode,
        duration_s=dur,
        cost_usd=(data or {}).get("total_cost_usd", (data or {}).get("cost_usd")),
        input_tokens=inp,
        output_tokens=usage.get("output_tokens") if usage else None,
        num_turns=(data or {}).get("num_turns"),
        error=None if res.returncode == 0 else (res.stderr[-500:] or "non-zero exit"),
    )


def _codex(harness, task, ws, log_dir, trial, prompt) -> AgentResult:
    # Best effort: `codex exec --json` emits JSONL events; we sum any usage blocks found.
    cmd = ["codex", "exec", "--json"]
    if harness.model:
        cmd += ["-m", harness.model]
    cmd += harness.extra_args + [prompt]
    res, dur, err = _exec(cmd, ws, log_dir, harness, task.timeout_s, prompt)
    if err:
        return AgentResult(False, None, dur, error=err)
    inp = out = 0
    found = False
    for line in res.stdout.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        for usage in _find_usage(ev):
            found = True
            inp += int(usage.get("input_tokens") or 0)
            out += int(usage.get("output_tokens") or 0)
    return AgentResult(res.returncode == 0, res.returncode, dur,
                       input_tokens=inp if found else None, output_tokens=out if found else None,
                       error=None if res.returncode == 0 else res.stderr[-500:])


def _command(harness, task, ws, log_dir, trial, prompt) -> AgentResult:
    """Generic adapter for any CLI agent (opencode, aider, ...). Placeholders:
    {prompt} {model} {workspace}. Telemetry: if the command writes .hev/usage.json
    with cost_usd/input_tokens/output_tokens, it is picked up."""
    if not harness.command:
        raise SystemExit(f"harness {harness.name}: agent=command requires `command = [...]`")
    cmd = [c.format(prompt=prompt, model=harness.model or "", workspace=str(ws)) for c in harness.command]
    res, dur, err = _exec(cmd, ws, log_dir, harness, task.timeout_s, prompt)
    if err:
        return AgentResult(False, None, dur, error=err)
    usage = {}
    up = ws / ".hev" / "usage.json"
    if up.exists():
        usage = json.loads(up.read_text())
    return AgentResult(res.returncode == 0, res.returncode, dur, usage.get("cost_usd"),
                       usage.get("input_tokens"), usage.get("output_tokens"), usage.get("num_turns"),
                       None if res.returncode == 0 else res.stderr[-500:])


def _replay(harness, task, ws, log_dir, trial, prompt) -> AgentResult:
    """Deterministic fake agent used by the self-test: copies a pre-written
    solution over the workspace. Lets us plant a KNOWN quality difference and
    check that the evaluator detects it (and reports nothing on an A/A run)."""
    src = (harness.solutions or harness.root / "solutions") / task.id
    if not src.exists():
        return AgentResult(False, 1, 0.0, error=f"no replay solution for {task.id}")
    meta = {}
    for p in src.rglob("*"):
        if p.is_file():
            rel = p.relative_to(src)
            if rel.name == "_meta.json":
                meta = json.loads(p.read_text())
                continue
            dest = ws / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest)
    # Simulated run-to-run noise on cost (agents are not deterministic in cost).
    seed = int(hashlib.sha256(f"{harness.name}/{task.id}/{trial}".encode()).hexdigest(), 16) % 2**32
    rng = random.Random(seed)
    jitter = 1 + rng.uniform(-0.2, 0.2)
    base_cost = float(meta.get("cost_usd", 0.10))
    return AgentResult(True, 0, round(float(meta.get("duration_s", 60)) * jitter, 2),
                       cost_usd=round(base_cost * jitter, 4),
                       input_tokens=int(meta.get("input_tokens", 20000) * jitter),
                       output_tokens=int(meta.get("output_tokens", 2000) * jitter),
                       num_turns=meta.get("num_turns", 8))


def _last_json(text: str) -> dict | None:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for line in reversed(text.splitlines()):
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


def _find_usage(obj):
    if isinstance(obj, dict):
        if "input_tokens" in obj or "output_tokens" in obj:
            yield obj
            return
        for v in obj.values():
            yield from _find_usage(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _find_usage(v)
