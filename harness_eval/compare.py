"""Baseline vs candidate comparison.

Unit of analysis: the TASK. For each task we average the trials of each harness,
then take the paired difference (candidate - baseline) and average over tasks.
Uncertainty: hierarchical bootstrap (resample tasks, then trials within each task),
so the interval reflects both "which tasks we picked" and "agent run-to-run noise".

Each metric is then classified against a practical threshold (eps):
  better / worse   CI excludes 0 AND the effect is at least eps
  equivalent       whole CI inside [-eps, +eps]  -> we can claim "no meaningful change"
  negligible       CI excludes 0 but the effect is below eps
  inconclusive     anything else -> not enough evidence either way
"""
from __future__ import annotations

import hashlib
import random
from pathlib import Path

from .config import Harness

# key, label, higher_is_better, eps, relative, role
METRICS = [
    ("resolved", "Tasks fully resolved (hidden tests + suite green)", True, 0.05, False, "quality"),
    ("hidden_pass_rate", "Hidden acceptance tests passed", True, 0.03, False, "quality"),
    ("conventions", "Team conventions adherence", True, 0.03, False, "quality"),
    ("requirements", "Business requirements met (LLM judge)", True, 0.05, False, "quality"),
    ("cost_usd", "Cost per task (USD)", False, 0.05, True, "cost"),
    ("output_tokens", "Output tokens per task", False, 0.05, True, "info"),
    ("duration_s", "Wall time per task (s)", False, 0.10, True, "info"),
]


def _mean(xs):
    return sum(xs) / len(xs)


def _stat(a_lists, b_lists, relative):
    ma, mb = [_mean(x) for x in a_lists], [_mean(x) for x in b_lists]
    if relative:
        sa = sum(ma)
        return (sum(mb) / sa - 1) if sa else 0.0
    return _mean([y - x for x, y in zip(ma, mb)])


def bootstrap(a: dict[str, list[float]], b: dict[str, list[float]], relative: bool,
              iters: int = 2000, seed: int = 7):
    tasks = sorted(t for t in a if t in b and a[t] and b[t])
    if not tasks:
        return None
    point = _stat([a[t] for t in tasks], [b[t] for t in tasks], relative)
    rng = random.Random(seed)
    samples = []
    for _ in range(iters):
        ts = [rng.choice(tasks) for _ in tasks]
        samples.append(_stat([[rng.choice(a[t]) for _ in a[t]] for t in ts],
                             [[rng.choice(b[t]) for _ in b[t]] for t in ts], relative))
    samples.sort()
    return point, samples[int(0.025 * iters)], samples[int(0.975 * iters) - 1], len(tasks)


def classify(point, lo, hi, eps, higher_is_better) -> str:
    gp, glo, ghi = (point, lo, hi) if higher_is_better else (-point, -hi, -lo)
    if glo > 0 and gp >= eps:
        return "better"
    if ghi < 0 and gp <= -eps:
        return "worse"
    if glo >= -eps and ghi <= eps:
        return "equivalent"
    if glo > 0 or ghi < 0:
        return "negligible"
    return "inconclusive"


def _per_task(records, key):
    out: dict[str, list[float]] = {}
    for r in records:
        v = r["metrics"].get(key)
        if v is not None:
            out.setdefault(r["task"], []).append(float(v))
    return out


def _overlay_files(h: Harness) -> dict[str, str]:
    if not h.overlay:
        return {}
    return {str(p.relative_to(h.overlay)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(h.overlay.rglob("*")) if p.is_file()}


def harness_diff(a: Harness, b: Harness) -> dict:
    fa, fb = _overlay_files(a), _overlay_files(b)
    cfg = {}
    for k in ("agent", "model", "extra_args", "prompt_prefix", "env", "command", "solutions"):
        va, vb = getattr(a, k), getattr(b, k)
        if k == "solutions" and va and vb:
            va, vb = str(va.resolve()), str(vb.resolve())
        if va != vb:
            cfg[k] = {"baseline": str(va) if k == "solutions" else va,
                      "candidate": str(vb) if k == "solutions" else vb}
    return {
        "added": sorted(set(fb) - set(fa)),
        "removed": sorted(set(fa) - set(fb)),
        "modified": sorted(f for f in fa if f in fb and fa[f] != fb[f]),
        "config": cfg,
    }


def verdict(results: dict, max_cost_increase: float) -> tuple[str, str]:
    q = {k: v for k, v in results.items() if v and v["role"] == "quality"}
    better = [k for k, v in q.items() if v["class"] == "better"]
    worse = [k for k, v in q.items() if v["class"] == "worse"]
    unsure = [k for k, v in q.items() if v["class"] == "inconclusive"]
    cost = results.get("cost_usd")
    cost_cls = cost["class"] if cost else "n/a"
    cost_up = cost["point"] if cost else 0.0
    lbl = lambda ks: ", ".join(results[k]["label"].lower() for k in ks)
    if worse:
        return "NEGATIVE", f"Quality regressed: {lbl(worse)}. Do not roll out."
    if better:
        if cost_cls == "worse" and cost_up > max_cost_increase:
            return ("POSITIVE_WITH_COST_TRADEOFF",
                    f"Improved {lbl(better)}, but cost rose {cost_up:+.0%} (budget {max_cost_increase:+.0%}). "
                    f"Roll out only if the quality gain is worth the spend.")
        return "POSITIVE", f"Improved {lbl(better)} with no quality regression. Safe to roll out."
    if unsure:
        return ("INCONCLUSIVE",
                f"Not enough evidence on {lbl(unsure)}. Add tasks or trials before deciding.")
    if cost_cls == "better":
        return "POSITIVE", f"Same quality, cost {cost_up:+.0%}. Safe to roll out."
    if cost_cls == "worse":
        return "NEGATIVE", f"No quality gain, but cost {cost_up:+.0%}. Not worth rolling out."
    return "NEUTRAL", "No measurable effect on quality or cost. The change is harmless but not proven useful."


def compare(base_recs, cand_recs, hb: Harness, hc: Harness, max_cost_increase: float) -> dict:
    results = {}
    for key, label, hib, eps, rel, role in METRICS:
        a, b = _per_task(base_recs, key), _per_task(cand_recs, key)
        bs = bootstrap(a, b, rel)
        if not bs:
            results[key] = None
            continue
        point, lo, hi, n = bs
        results[key] = {
            "label": label, "role": role, "relative": rel, "eps": eps, "higher_is_better": hib,
            "baseline": _mean([_mean(v) for v in a.values()]),
            "candidate": _mean([_mean(v) for v in b.values()]),
            "point": point, "lo": lo, "hi": hi, "n_tasks": n,
            "class": classify(point, lo, hi, eps, hib),
        }
    v, reason = verdict(results, max_cost_increase)
    return {"verdict": v, "reason": reason, "metrics": results, "harness_diff": harness_diff(hb, hc),
            "baseline": hb.name, "candidate": hc.name}
