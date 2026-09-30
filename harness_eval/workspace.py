"""Each trial gets a fresh copy of the task repo with the harness overlay applied,
committed as the 'before' state, so the agent's work is exactly `git diff`."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .config import Harness, Task

_IGNORE = shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc", ".git")
_EXCLUDES = "__pycache__/\n.pytest_cache/\n*.pyc\n.hev/\n"


def git(cwd: Path, *args: str) -> str:
    res = subprocess.run(
        ["git", "-c", "user.email=hev@localhost", "-c", "user.name=hev", "-c", "core.autocrlf=false", *args],
        cwd=cwd, capture_output=True, text=True,
    )
    if res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {res.stderr}")
    return res.stdout


def prepare_workspace(task: Task, harness: Harness, ws: Path) -> None:
    shutil.copytree(task.repo, ws, ignore=_IGNORE)
    if harness.overlay:
        shutil.copytree(harness.overlay, ws, dirs_exist_ok=True, ignore=_IGNORE)
    git(ws, "init", "-q")
    (ws / ".git" / "info" / "exclude").write_text(_EXCLUDES)
    git(ws, "add", "-A")
    git(ws, "commit", "-q", "-m", "hev: baseline (task repo + harness overlay)")


def workspace_diff(ws: Path) -> str:
    git(ws, "add", "-A")
    return git(ws, "diff", "--cached", "HEAD", "--no-color", "--unified=3")


def changed_files(ws: Path) -> list[str]:
    git(ws, "add", "-A")
    out = git(ws, "diff", "--cached", "HEAD", "--name-only")
    return [l for l in out.splitlines() if l.strip()]


def diff_stats(diff: str) -> dict:
    added = sum(1 for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff.splitlines() if l.startswith("-") and not l.startswith("---"))
    files = sum(1 for l in diff.splitlines() if l.startswith("diff --git"))
    return {"files_changed": files, "lines_added": added, "lines_removed": removed}
