"""Runs (harness x task x trial). Every trial is isolated and fully recorded on disk:
prompt, agent stdout/stderr, diff.patch, test output, result.json. Results are
cached by (harness fingerprint, task fingerprint) so a baseline is run once and
reused across many candidate comparisons, and is re-run automatically if either
the harness or the task changes."""
from __future__ import annotations

import json
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .agents import run_agent
from .config import Harness, Suite, Task
from .graders import grade_conventions, grade_functional
from .judge import JudgeConfig, judge
from .workspace import changed_files, diff_stats, prepare_workspace, workspace_diff


def trial_dir(out: Path, suite: Suite, harness: Harness, task: Task, i: int) -> Path:
    return out / suite.name / harness.name / task.id / f"trial-{i}"


def run_trial(suite: Suite, task: Task, harness: Harness, i: int, tdir: Path, jcfg: JudgeConfig, fp: dict) -> dict:
    if tdir.exists():
        shutil.rmtree(tdir)
    tdir.mkdir(parents=True)
    ws = tdir / "workspace"
    prepare_workspace(task, harness, ws)
    agent = run_agent(harness, task, ws, tdir, i)
    diff = workspace_diff(ws)
    (tdir / "diff.patch").write_text(diff)
    changed = changed_files(ws)
    func = grade_functional(task, ws, tdir)
    empty = not diff.strip()
    conv = grade_conventions(suite.rules + task.rules, diff, changed)
    jres = None if empty else judge(task.prompt, task.rubric, diff, jcfg)
    requirements = 0.0 if (empty and task.rubric and jcfg.resolved_mode() != "off") else (jres or {}).get("score")
    metrics = {
        # An agent that changed nothing must not look good on any quality axis.
        "resolved": 1.0 if (func["hidden_pass_rate"] == 1.0 and func["visible_green"]) else 0.0,
        "hidden_pass_rate": func["hidden_pass_rate"],
        "conventions": 0.0 if empty else conv["score"],
        "requirements": requirements,
        "cost_usd": agent.cost_usd,
        "duration_s": agent.duration_s,
        "input_tokens": agent.input_tokens,
        "output_tokens": agent.output_tokens,
    }
    rec = {
        "suite": suite.name, "harness": harness.name, "task": task.id, "trial": i,
        "fingerprint": fp, "metrics": metrics, "agent": agent.to_dict(),
        "functional": func, "conventions": conv, "judge": jres,
        "diff": {**diff_stats(diff), "files": changed, "empty": empty},
    }
    (tdir / "result.json").write_text(json.dumps(rec, indent=2))
    return rec


def run_harness(suite: Suite, harness: Harness, trials: int, out: Path, jobs: int,
                jcfg: JudgeConfig, fresh: bool = False, log=print) -> list[dict]:
    hfp = harness.fingerprint()
    jobs_todo, records = [], []
    for task in suite.tasks:
        fp = {"harness": hfp, "task": task.fingerprint(), "judge": f"{jcfg.resolved_mode()}:{jcfg.model}:{jcfg.samples}"}
        for i in range(trials):
            tdir = trial_dir(out, suite, harness, task, i)
            cached = tdir / "result.json"
            if not fresh and cached.exists():
                rec = json.loads(cached.read_text())
                if rec.get("fingerprint") == fp:
                    records.append(rec)
                    continue
            jobs_todo.append((task, i, tdir, fp))
    if records:
        log(f"  [{harness.name}] reusing {len(records)} cached trial(s)")
    if jobs_todo:
        log(f"  [{harness.name}] running {len(jobs_todo)} trial(s) with {jobs} worker(s)...")
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        futs = {pool.submit(run_trial, suite, t, harness, i, d, jcfg, fp): (t.id, i) for t, i, d, fp in jobs_todo}
        for f in as_completed(futs):
            tid, i = futs[f]
            try:
                rec = f.result()
            except Exception as ex:
                print(f"  [{harness.name}] {tid} trial {i}: CRASHED {ex!r}", file=sys.stderr)
                raise
            m = rec["metrics"]
            status = "resolved" if m["resolved"] else "not resolved"
            err = f" (agent error: {rec['agent']['error']})" if rec["agent"]["error"] else ""
            log(f"  [{harness.name}] {tid} #{i}: {status}, hidden {m['hidden_pass_rate']:.0%}, "
                f"conventions {m['conventions']:.0%}{err}")
            records.append(rec)
    return sorted(records, key=lambda r: (r["task"], r["trial"]))
