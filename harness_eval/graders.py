"""Deterministic graders.

functional  - hidden acceptance tests (copied in only AFTER the agent finished,
              so the agent cannot read or edit them) + the repo's own suite.
conventions - the team's rules, evaluated on lines the agent ADDED only, so
              pre-existing debt in the repo is never blamed on the harness.
"""
from __future__ import annotations

import fnmatch
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from .config import Rule, Task


def _run(cmd: str, cwd: Path, timeout: int) -> tuple[int, str]:
    try:
        res = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True, timeout=timeout)
        return res.returncode, (res.stdout + res.stderr)[-4000:]
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def _junit(path: Path, exit_code: int) -> tuple[int, int]:
    if not path.exists():
        return (1, 1) if exit_code == 0 else (0, 1)
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    total = failed = 0
    for s in suites:
        total += int(s.get("tests", 0))
        failed += int(s.get("failures", 0)) + int(s.get("errors", 0))
        total -= int(s.get("skipped", 0))
    if total <= 0:
        return (0, 1)  # collection error / nothing ran counts as a failure
    return total - failed, total


def grade_functional(task: Task, ws: Path, art: Path) -> dict:
    cmd = task.test_cmd.format(python=sys.executable)
    # 1) The repo's own suite (existing tests + whatever tests the agent wrote).
    vis_xml = art / "visible_junit.xml"
    code, out = _run(f"{cmd} --junitxml={vis_xml}", ws, 600)
    (art / "visible_tests.txt").write_text(out)
    vis_passed, vis_total = _junit(vis_xml, code)
    # 2) Hidden acceptance tests.
    dest = ws / task.hidden_dest
    if dest.exists():
        shutil.rmtree(dest)  # agent must not be able to pre-seed this path
    shutil.copytree(task.hidden_tests, dest)
    hid_xml = art / "hidden_junit.xml"
    code_h, out_h = _run(f"{cmd} {task.hidden_dest} --junitxml={hid_xml}", ws, 600)
    (art / "hidden_tests.txt").write_text(out_h)
    passed, total = _junit(hid_xml, code_h)
    shutil.rmtree(dest, ignore_errors=True)
    return {
        "hidden_passed": passed,
        "hidden_total": total,
        "hidden_pass_rate": passed / total,
        "visible_passed": vis_passed,
        "visible_total": vis_total,
        "visible_green": code == 0,
    }


def _match(path: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, g) for g in globs)


def added_lines(diff: str) -> dict[str, list[tuple[int, str]]]:
    files: dict[str, list[tuple[int, str]]] = {}
    cur, lineno = None, 0
    for line in diff.splitlines():
        if line.startswith("+++ "):
            cur = line[6:] if line.startswith("+++ b/") else None
            if cur:
                files.setdefault(cur, [])
        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            lineno = int(m.group(1)) if m else 0
        elif cur is not None and line.startswith("+"):
            files[cur].append((lineno, line[1:]))
            lineno += 1
        elif cur is not None and not line.startswith("-"):
            lineno += 1
    return files


def grade_conventions(rules: list[Rule], diff: str, changed: list[str]) -> dict:
    added = added_lines(diff)
    results, violations = [], []
    for r in rules:
        if r.kind == "forbid":
            rx = re.compile(r.pattern or "")
            hits = [
                {"rule": r.id, "file": f, "line": n, "text": t.strip()[:160], "message": r.message}
                for f, lines in added.items() if _match(f, r.paths)
                for n, t in lines if rx.search(t)
            ]
            applicable = any(_match(f, r.paths) for f in added)
            violations += hits
            results.append({"rule": r.id, "applicable": applicable, "passed": not hits})
        elif r.kind == "require_change":
            triggered = not r.when_changed or any(_match(f, r.when_changed) for f in changed)
            ok = any(_match(f, r.paths) for f in changed)
            if triggered and not ok:
                violations.append({"rule": r.id, "file": "-", "line": 0, "text": "", "message": r.message})
            results.append({"rule": r.id, "applicable": triggered, "passed": ok or not triggered})
    applicable = [x for x in results if x["applicable"]]
    score = (sum(x["passed"] for x in applicable) / len(applicable)) if applicable else 1.0
    return {"score": score, "rules": results, "violations": violations}
