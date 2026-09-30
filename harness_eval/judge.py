"""Rubric-based LLM judge for 'does it do what the business asked'.

Design choices that matter for trust:
- Binary criteria, not a 1-10 score: easier to agree with, easier to audit.
- The judge is BLIND: it never sees which harness produced the diff, and it runs
  in an empty temp dir so a candidate's AGENTS.md cannot influence it.
- Optional repeated sampling (--judge-samples) + majority vote; the agreement
  rate between samples is reported so a noisy judge is visible in the report.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import urllib.request
from dataclasses import dataclass

MAX_DIFF_CHARS = 60_000

PROMPT = """You are a strict senior reviewer checking a code change against business requirements.

## Request given to the engineer
{prompt}

## Acceptance criteria
{criteria}

## The code change (unified diff)
```diff
{diff}
```

For EACH criterion decide whether the diff fully satisfies it. Judge only what the diff shows.
If the diff does not clearly implement a criterion, it is NOT met.
Respond with ONLY this JSON, no prose, no markdown fences:
{{"criteria": [{{"id": 1, "met": true, "evidence": "<one short sentence>"}}]}}"""


@dataclass
class JudgeConfig:
    mode: str = "auto"  # auto | api | claude-cli | off
    model: str | None = None
    samples: int = 1

    def resolved_mode(self) -> str:
        if self.mode != "auto":
            return self.mode
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "api"
        if shutil.which("claude"):
            return "claude-cli"
        return "off"


def _call_api(prompt: str, model: str) -> str:
    body = json.dumps({
        "model": model, "max_tokens": 2000, "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body, method="POST",
        headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read())
    return "".join(b.get("text", "") for b in data.get("content", []))


def _call_cli(prompt: str, model: str) -> str:
    with tempfile.TemporaryDirectory() as empty:  # no repo, no AGENTS.md: blind judge
        res = subprocess.run(["claude", "-p", prompt, "--output-format", "json", "--model", model],
                             cwd=empty, capture_output=True, text=True, timeout=300)
    data = json.loads(res.stdout)
    return data.get("result", "")


def _parse(text: str, n: int) -> list[bool]:
    start, end = text.find("{"), text.rfind("}")
    data = json.loads(text[start:end + 1])
    by_id = {int(c["id"]): (bool(c["met"]), c.get("evidence", "")) for c in data["criteria"]}
    return [by_id.get(i + 1, (False, ""))[0] for i in range(n)], [by_id.get(i + 1, (False, ""))[1] for i in range(n)]


def judge(task_prompt: str, rubric: list[str], diff: str, cfg: JudgeConfig) -> dict | None:
    mode = cfg.resolved_mode()
    if mode == "off" or not rubric:
        return None
    model = cfg.model or ("claude-sonnet-4-5" if mode == "api" else "sonnet")
    criteria = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(rubric))
    prompt = PROMPT.format(prompt=task_prompt, criteria=criteria, diff=diff[:MAX_DIFF_CHARS])
    votes, evidence, errors = [], [], []
    for _ in range(max(1, cfg.samples)):
        try:
            text = _call_api(prompt, model) if mode == "api" else _call_cli(prompt, model)
            v, e = _parse(text, len(rubric))
            votes.append(v)
            evidence.append(e)
        except Exception as ex:  # a failed judge call must never crash the run
            errors.append(repr(ex)[:300])
    if not votes:
        return {"score": None, "error": errors, "backend": mode, "model": model}
    per_crit = []
    for i, c in enumerate(rubric):
        yes = sum(v[i] for v in votes)
        per_crit.append({"criterion": c, "met": yes * 2 > len(votes), "yes_votes": yes,
                         "samples": len(votes), "evidence": evidence[0][i]})
    agreement = sum(1 for i in range(len(rubric)) if len({v[i] for v in votes}) == 1) / len(rubric)
    return {
        "score": sum(c["met"] for c in per_crit) / len(rubric),
        "criteria": per_crit,
        "agreement": agreement if len(votes) > 1 else None,
        "backend": mode, "model": model, "errors": errors,
    }
