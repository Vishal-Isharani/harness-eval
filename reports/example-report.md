# Harness evaluation: `baseline` → `candidate-conventions-skill`

## ❔ Verdict: **INCONCLUSIVE**

Not enough evidence on team conventions adherence, business requirements met (llm judge). Add tasks or trials before deciding.

## What changed in the harness

- added: `.claude/skills/money-arithmetic/SKILL.md`
- modified: `AGENTS.md`

## Scorecard

Averages are per task (mean of 3 trial(s) each), then across tasks. Δ is candidate − baseline, paired by task; CI is a 95% hierarchical bootstrap.

| Metric | baseline | candidate-conventions-skill | Δ | 95% CI | Result |
|---|---|---|---|---|---|
| Tasks fully resolved (hidden tests + suite green) | 0% | 0% | +0.0 pp | [+0.0, +0.0] pp | ➖ no meaningful change |
| Hidden acceptance tests passed | 0% | 0% | +0.0 pp | [+0.0, +0.0] pp | ➖ no meaningful change |
| Team conventions adherence | 94% | 100% | +5.6 pp | [+0.0, +13.0] pp | ❔ inconclusive |
| Business requirements met (LLM judge) | 97% | 100% | +2.8 pp | [+0.0, +11.1] pp | ❔ inconclusive |
| Cost per task (USD) | $0.092 | $0.104 | +13% | [+5%, +21%] | ❌ worse |
| Output tokens per task _(info)_ | 1,558 | 2,021 | +30% | [+11%, +60%] | ❌ worse |
| Wall time per task (s) _(info)_ | 17s | 20s | +16% | [+1%, +35%] | ❌ worse |

## Per-task breakdown

| Task | Resolved baseline | Resolved candidate-conventions-skill | Conventions baseline → candidate-conventions-skill | Requirements baseline → candidate-conventions-skill | Cost baseline → candidate-conventions-skill |
|---|---|---|---|---|---|
| `discount-codes` | 0/3 | 0/3 | 89% → 100% | 100% → 100% | $0.101 → $0.112 |
| `fix-tax-rounding` | 0/3 | 0/3 | 94% → 100% | 92% → 100% | $0.082 → $0.091 |
| `remove-item` | 0/3 | 0/3 | 100% → 100% | 100% → 100% | $0.094 → $0.109 |

## Convention violations (total across all trials)

| Rule | baseline | candidate-conventions-skill |
|---|---|---|
| `no-true-division` | 2 | 0 |
| `tests-accompany-changes` | 1 | 0 |

## Requirements the judge found unmet (count of trials)

| Task | Criterion | baseline | candidate-conventions-skill |
|---|---|---|---|
| `fix-tax-rounding` | A regression test that reproduces the reported 0.82 vs 0.84 discrepancy is added. | 1 | 0 |

## Reliability of this result

- Only **3 tasks**. The bootstrap over tasks is coarse with so few; treat this as a smoke test and grow the suite before trusting small effects.

## How to read this

- **better / worse**: the 95% CI excludes zero *and* the effect exceeds the practical threshold.
- **no meaningful change**: the whole CI sits inside the threshold, so we can positively say nothing changed.
- **inconclusive**: the CI is too wide to say either way. More tasks narrow it faster than more trials.
- Every number traces back to files under the run directory: `diff.patch`, `hidden_tests.txt`, `agent_stdout.txt` and `result.json` per trial.
