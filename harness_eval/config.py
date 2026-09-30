"""Loading of the three input concepts: Harness, Task and Suite.

Harness  = everything the team iterates on (agent CLI, model, AGENTS.md, skills,
           MCP config, hooks, prompt prefix). Represented as a directory whose
           `overlay/` is copied on top of the task repo before the agent runs.
Task     = a frozen repo snapshot + a business request + hidden acceptance
           tests + a requirements rubric. The agent never sees the hidden tests.
Suite    = a set of tasks + the team's conventions (rules), shared by all tasks.
"""
from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Rule:
    id: str
    kind: str  # "forbid" | "require_change"
    paths: list[str]
    message: str
    pattern: str | None = None  # forbid: regex applied to ADDED lines only
    when_changed: list[str] = field(default_factory=list)  # require_change trigger


@dataclass
class Harness:
    name: str
    root: Path
    agent: str  # claude-code | codex | command | replay
    model: str | None
    overlay: Path | None
    extra_args: list[str]
    env: dict[str, str]
    command: list[str] | None
    prompt_prefix: str
    solutions: Path | None

    def fingerprint(self) -> str:
        return _dir_hash(self.root)


@dataclass
class Task:
    id: str
    root: Path
    prompt: str
    repo: Path
    hidden_tests: Path
    hidden_dest: str
    test_cmd: str
    timeout_s: int
    rubric: list[str]
    rules: list[Rule]

    def fingerprint(self) -> str:
        return hashlib.sha256((_dir_hash(self.root) + _dir_hash(self.repo)).encode()).hexdigest()[:16]


@dataclass
class Suite:
    name: str
    root: Path
    tasks: list[Task]
    rules: list[Rule]


def _dir_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and ".pytest_cache" not in p.parts:
            h.update(str(p.relative_to(root)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()[:16]


def _rules(raw: list[dict]) -> list[Rule]:
    out = []
    for r in raw:
        out.append(
            Rule(
                id=r["id"],
                kind=r.get("kind", "forbid"),
                paths=r.get("paths", ["*"]),
                message=r.get("message", r["id"]),
                pattern=r.get("pattern"),
                when_changed=r.get("when_changed", []),
            )
        )
    return out


def load_harness(path: str | Path) -> Harness:
    p = Path(path)
    if p.is_dir():
        p = p / "harness.toml"
    d = tomllib.loads(p.read_text())
    root = p.parent.resolve()
    overlay = root / d.get("overlay", "overlay")
    solutions = d.get("solutions")
    return Harness(
        name=d.get("name", root.name),
        root=root,
        agent=d.get("agent", "claude-code"),
        model=d.get("model"),
        overlay=overlay if overlay.exists() else None,
        extra_args=list(d.get("extra_args", [])),
        env={k: str(v) for k, v in d.get("env", {}).items()},
        command=d.get("command"),
        prompt_prefix=d.get("prompt_prefix", ""),
        solutions=(root / solutions) if solutions else None,
    )


def load_task(path: Path) -> Task:
    d = tomllib.loads(path.read_text())
    root = path.parent.resolve()
    return Task(
        id=d.get("id", root.name),
        root=root,
        prompt=d["prompt"].strip(),
        repo=(root / d["repo"]).resolve(),
        hidden_tests=(root / d.get("hidden_tests", "hidden_tests")).resolve(),
        hidden_dest=d.get("hidden_dest", "tests/_hidden_hev"),
        test_cmd=d.get("test_cmd", "{python} -m pytest -q -p no:cacheprovider"),
        timeout_s=int(d.get("timeout_s", 900)),
        rubric=list(d.get("rubric", [])),
        rules=_rules(d.get("rules", [])),
    )


def load_suite(path: str | Path, only: list[str] | None = None) -> Suite:
    p = Path(path)
    if p.is_dir():
        p = p / "suite.toml"
    d = tomllib.loads(p.read_text())
    root = p.parent.resolve()
    tasks = [load_task(t) for t in sorted(root.glob(d.get("tasks", "tasks/*/task.toml")))]
    if only:
        tasks = [t for t in tasks if t.id in only]
    if not tasks:
        raise SystemExit(f"No tasks found in suite {p}")
    return Suite(name=d.get("name", root.name), root=root, tasks=tasks, rules=_rules(d.get("rules", [])))
