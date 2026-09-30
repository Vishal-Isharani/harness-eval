from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

ICON = {"better": "✅ better", "worse": "❌ worse", "equivalent": "➖ no meaningful change",
        "negligible": "➖ negligible", "inconclusive": "❔ inconclusive"}
VERDICT_ICON = {"POSITIVE": "✅", "POSITIVE_WITH_COST_TRADEOFF": "⚖️", "NEGATIVE": "❌",
                "NEUTRAL": "➖", "INCONCLUSIVE": "❔"}


def _fmt(v, key):
    if v is None:
        return "n/a"
    if key == "cost_usd":
        return f"${v:.3f}"
    if key in ("duration_s",):
        return f"{v:.0f}s"
    if key.endswith("tokens"):
        return f"{v:,.0f}"
    return f"{v:.0%}"


def _delta(m):
    if m["relative"]:
        return f"{m['point']:+.0%}", f"[{m['lo']:+.0%}, {m['hi']:+.0%}]"
    return f"{m['point'] * 100:+.1f} pp", f"[{m['lo'] * 100:+.1f}, {m['hi'] * 100:+.1f}] pp"


def _by_task(recs):
    d = defaultdict(list)
    for r in recs:
        d[r["task"]].append(r)
    return d


def _avg(rs, key):
    vals = [r["metrics"][key] for r in rs if r["metrics"].get(key) is not None]
    return sum(vals) / len(vals) if vals else None


def _top_violations(recs, k=3):
    """Most frequent rules, ranked by violations, then trials hit, then rule id."""
    by_rule = defaultdict(list)
    for r in recs:
        for v in r["conventions"]["violations"]:
            by_rule[v["rule"]].append(((r["task"], r["trial"], v["file"], v["line"]), v))
    top = []
    for rule, hits in by_rule.items():
        hits.sort(key=lambda h: h[0])
        located = [v for _, v in hits if v["line"] > 0]
        top.append({"rule": rule, "count": len(hits),
                    "trials": len({key[:2] for key, _ in hits}),
                    "example": located[0] if located else hits[0][1]})
    top.sort(key=lambda t: (-t["count"], -t["trials"], t["rule"]))
    return top[:k]


def _code(s):
    return f"`` {s} ``" if "`" in s else f"`{s}`"


def build_markdown(cmp: dict, base: list[dict], cand: list[dict], trials: int) -> str:
    A, B = cmp["baseline"], cmp["candidate"]
    L = [f"# Harness evaluation: `{A}` → `{B}`", "",
         f"## {VERDICT_ICON.get(cmp['verdict'], '')} Verdict: **{cmp['verdict']}**", "", cmp["reason"], ""]

    hd = cmp["harness_diff"]
    L += ["## What changed in the harness", ""]
    if not any([hd["added"], hd["removed"], hd["modified"], hd["config"]]):
        L.append("_No difference in overlay files or agent config. This is an A/A run: "
                 "any effect below is noise, and the verdict should be NEUTRAL._")
    for k in ("added", "removed", "modified"):
        for f in hd[k]:
            L.append(f"- {k}: `{f}`")
    for k, v in hd["config"].items():
        L.append(f"- config `{k}`: `{v['baseline']}` → `{v['candidate']}`")
    L.append("")

    L += ["## Scorecard", "",
          f"Averages are per task (mean of {trials} trial(s) each), then across tasks. "
          "Δ is candidate − baseline, paired by task; CI is a 95% hierarchical bootstrap.", "",
          f"| Metric | {A} | {B} | Δ | 95% CI | Result |", "|---|---|---|---|---|---|"]
    for key, m in cmp["metrics"].items():
        if not m:
            L.append(f"| {key} | n/a | n/a | | | not measured |")
            continue
        d, ci = _delta(m)
        role = "" if m["role"] != "info" else " _(info)_"
        L.append(f"| {m['label']}{role} | {_fmt(m['baseline'], key)} | {_fmt(m['candidate'], key)} "
                 f"| {d} | {ci} | {ICON[m['class']]} |")
    L.append("")

    bt, ct = _by_task(base), _by_task(cand)
    L += ["## Per-task breakdown", "",
          f"| Task | Resolved {A} | Resolved {B} | Conventions {A} → {B} | Requirements {A} → {B} | Cost {A} → {B} |",
          "|---|---|---|---|---|---|"]
    for t in sorted(set(bt) | set(ct)):
        ra, rb = bt.get(t, []), ct.get(t, [])
        res = lambda rs: f"{sum(int(r['metrics']['resolved']) for r in rs)}/{len(rs)}"
        L.append(f"| `{t}` | {res(ra)} | {res(rb)} | {_fmt(_avg(ra, 'conventions'), 'c')} → {_fmt(_avg(rb, 'conventions'), 'c')} "
                 f"| {_fmt(_avg(ra, 'requirements'), 'r')} → {_fmt(_avg(rb, 'requirements'), 'r')} "
                 f"| {_fmt(_avg(ra, 'cost_usd'), 'cost_usd')} → {_fmt(_avg(rb, 'cost_usd'), 'cost_usd')} |")
    L.append("")

    va = Counter(v["rule"] for r in base for v in r["conventions"]["violations"])
    vb = Counter(v["rule"] for r in cand for v in r["conventions"]["violations"])
    if va or vb:
        L += ["## Convention violations (total across all trials)", "",
              f"| Rule | {A} | {B} |", "|---|---|---|"]
        for rule in sorted(set(va) | set(vb), key=lambda x: -(va[x] + vb[x])):
            L.append(f"| `{rule}` | {va[rule]} | {vb[rule]} |")
        L += ["", "### Most frequent rules, with an example", ""]
        for name, recs in ((A, base), (B, cand)):
            L += [f"**{name}**", ""]
            for i, t in enumerate(_top_violations(recs), 1):
                ex = t["example"]
                loc = f"{ex['file']}:{ex['line']}"
                where = (f"{_code(loc)}: {_code(ex['text'])}" if ex["line"] > 0
                         else f"_no file/line_: {ex['message']}")
                L.append(f"{i}. `{t['rule']}`: {t['count']} violation(s) in {t['trials']}/{len(recs)} trials, "
                         f"e.g. {where}")
            if not any(r["conventions"]["violations"] for r in recs):
                L.append("_No violations._")
            L.append("")

    def missed(recs):
        c = Counter()
        for r in recs:
            for crit in (r.get("judge") or {}).get("criteria", []) or []:
                if not crit["met"]:
                    c[(r["task"], crit["criterion"])] += 1
        return c
    ma, mb = missed(base), missed(cand)
    if ma or mb:
        L += ["## Requirements the judge found unmet (count of trials)", "",
              f"| Task | Criterion | {A} | {B} |", "|---|---|---|---|"]
        for (t, c) in sorted(set(ma) | set(mb)):
            L.append(f"| `{t}` | {c} | {ma[(t, c)]} | {mb[(t, c)]} |")
        L.append("")

    L += ["## Reliability of this result", ""]
    n_tasks = len(set(bt) | set(ct))
    warn = []
    if n_tasks < 10:
        warn.append(f"Only **{n_tasks} tasks**. The bootstrap over tasks is coarse with so few; "
                    "treat this as a smoke test and grow the suite before trusting small effects.")
    if trials < 3:
        warn.append(f"Only **{trials} trial(s)** per task: run-to-run agent variance is barely sampled.")
    errs = sum(1 for r in base + cand if r["agent"]["error"])
    if errs:
        warn.append(f"**{errs} trial(s) had agent errors** (counted as failures, not dropped). Check the logs.")
    empties = sum(1 for r in base + cand if r["diff"]["empty"])
    if empties:
        warn.append(f"**{empties} trial(s) produced no change at all** (scored 0 on every quality axis).")
    flaky = [t for t in sorted(set(bt) | set(ct))
             for rs in (bt.get(t, []), ct.get(t, []))
             if len({r['metrics']['resolved'] for r in rs}) > 1]
    if flaky:
        warn.append("Tasks where trials of the same harness disagree (agent non-determinism): "
                    + ", ".join(f"`{t}`" for t in sorted(set(flaky))) + ".")
    agree = [r["judge"]["agreement"] for r in base + cand if r.get("judge") and r["judge"].get("agreement") is not None]
    if agree:
        a = sum(agree) / len(agree)
        warn.append(f"Judge self-agreement across samples: **{a:.0%}**"
                    + (" — below 90%, the requirements score is noisy; tighten the rubric." if a < 0.9 else "."))
    if not cmp["metrics"].get("requirements"):
        warn.append("Requirements (LLM judge) was **not measured** (judge off or no rubric). "
                    "The verdict relies on tests, conventions and cost only.")
    L += [f"- {w}" for w in warn] or ["- No reliability warnings."]
    L += ["", "## How to read this", "",
          "- **better / worse**: the 95% CI excludes zero *and* the effect exceeds the practical threshold.",
          "- **no meaningful change**: the whole CI sits inside the threshold, so we can positively say nothing changed.",
          "- **inconclusive**: the CI is too wide to say either way. More tasks narrow it faster than more trials.",
          "- Every number traces back to files under the run directory: `diff.patch`, `hidden_tests.txt`, "
          "`agent_stdout.txt` and `result.json` per trial.", ""]
    return "\n".join(L)


def write_report(cmp: dict, base, cand, trials: int, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    md = out_dir / "report.md"
    md.write_text(build_markdown(cmp, base, cand, trials))
    (out_dir / "report.json").write_text(json.dumps(
        {**cmp, "baseline_trials": base, "candidate_trials": cand}, indent=2, default=str))
    return md
