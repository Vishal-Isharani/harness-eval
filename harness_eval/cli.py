from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .compare import compare
from .config import load_harness, load_suite
from .judge import JudgeConfig
from .report import write_report
from .runner import run_harness

EXIT = {"POSITIVE": 0, "NEUTRAL": 0, "POSITIVE_WITH_COST_TRADEOFF": 2, "NEGATIVE": 1, "INCONCLUSIVE": 3}
EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _common(sp):
    sp.add_argument("--suite", required=True, help="suite dir (contains suite.toml)")
    sp.add_argument("--trials", type=int, default=3, help="runs per task per harness (default 3)")
    sp.add_argument("--out", default="runs", help="where trial artefacts are stored (default ./runs)")
    sp.add_argument("--jobs", type=int, default=2, help="parallel trials (default 2)")
    sp.add_argument("--tasks", help="comma-separated subset of task ids")
    sp.add_argument("--judge", choices=["auto", "api", "claude-cli", "off"], default="auto")
    sp.add_argument("--judge-model", default=None)
    sp.add_argument("--judge-samples", type=int, default=1, help="judge votes per trial (>=3 to measure judge noise)")
    sp.add_argument("--fresh", action="store_true", help="ignore cached trial results")


def _evaluate(suite_path, baseline, candidate, trials, out, jobs, jcfg, max_cost, report_dir,
              tasks=None, fresh=False, quiet=False):
    log = (lambda *_: None) if quiet else print
    suite = load_suite(suite_path, tasks)
    hb, hc = load_harness(baseline), load_harness(candidate)
    if hb.name == hc.name:
        raise SystemExit("baseline and candidate must have different `name` in harness.toml")
    log(f"Suite '{suite.name}': {len(suite.tasks)} task(s) x {trials} trial(s); judge={jcfg.resolved_mode()}")
    base = run_harness(suite, hb, trials, Path(out), jobs, jcfg, fresh, log)
    cand = run_harness(suite, hc, trials, Path(out), jobs, jcfg, fresh, log)
    cmp = compare(base, cand, hb, hc, max_cost)
    rdir = Path(report_dir) if report_dir else Path(out) / suite.name / f"report__{hb.name}__vs__{hc.name}"
    md = write_report(cmp, base, cand, trials, rdir)
    return cmp, md


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="hev", description="Evaluate whether a coding-agent harness change helps.")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run one harness on a suite (results are cached for later evaluate)")
    _common(r)
    r.add_argument("--harness", required=True)

    e = sub.add_parser("evaluate", help="baseline vs candidate -> report + verdict")
    _common(e)
    e.add_argument("--baseline", required=True)
    e.add_argument("--candidate", required=True)
    e.add_argument("--max-cost-increase", type=float, default=0.25,
                   help="relative cost increase tolerated for a quality gain (default 0.25 = +25%%)")
    e.add_argument("--report-dir", default=None)

    sub.add_parser("selftest", help="verify the evaluator on planted differences (no agent/API needed)")

    a = p.parse_args(argv)
    if a.cmd == "selftest":
        return selftest()
    jcfg = JudgeConfig(a.judge, a.judge_model, a.judge_samples)
    tasks = a.tasks.split(",") if a.tasks else None
    if a.cmd == "run":
        suite = load_suite(a.suite, tasks)
        run_harness(suite, load_harness(a.harness), a.trials, Path(a.out), a.jobs, jcfg, a.fresh)
        return 0
    cmp, md = _evaluate(a.suite, a.baseline, a.candidate, a.trials, a.out, a.jobs, jcfg,
                        a.max_cost_increase, a.report_dir, tasks, a.fresh)
    print(f"\nVERDICT: {cmp['verdict']} — {cmp['reason']}\nReport: {md}")
    return EXIT[cmp["verdict"]]


def selftest() -> int:
    """Known-answer tests for the evaluator itself. If these fail, no report is trustworthy."""
    import tempfile
    suite = EXAMPLES / "suite"
    h = EXAMPLES / "selftest" / "harnesses"
    cases = [
        ("A/A: identical harness must not show an effect", h / "good", h / "good-again", {"NEUTRAL"}),
        ("planted improvement must be detected", h / "sloppy", h / "good", {"POSITIVE", "POSITIVE_WITH_COST_TRADEOFF"}),
        ("planted regression must be detected", h / "good", h / "sloppy", {"NEGATIVE"}),
    ]
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        for name, base, cand, expected in cases:
            cmp, md = _evaluate(suite, base, cand, 3, tmp, 4, JudgeConfig("off"), 0.25, None, quiet=True)
            passed = cmp["verdict"] in expected
            ok &= passed
            print(f"{'PASS' if passed else 'FAIL'}  {name}: got {cmp['verdict']} (expected {'/'.join(sorted(expected))})")
            if not passed:
                print(md.read_text())
    print("selftest OK" if ok else "selftest FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
