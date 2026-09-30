# hev — did that harness change actually help?

`hev` answers one question for whoever maintains a team's coding-agent harness
(AGENTS.md / CLAUDE.md, skills, MCP config, hooks, workflow prompt, model, or the agent itself):

> **Is the agent producing better code after this change, or not?**

It runs the **baseline** and the **candidate** harness on the same suite of real
tasks, several times each, grades every run on **correctness, team conventions,
business requirements and cost**, and produces a report with a verdict backed by
confidence intervals: `POSITIVE`, `POSITIVE_WITH_COST_TRADEOFF`, `NEGATIVE`,
`NEUTRAL` or `INCONCLUSIVE`.

## Quick start (2 minutes, no API key, no agent)

```bash
git clone <this repo> && cd harness-eval
python3 -m venv .venv && source .venv/bin/activate   # Python 3.11+
pip install -e .
hev selftest
```

`selftest` checks the evaluator itself against known answers: an A/A run (identical
harnesses) must come out `NEUTRAL`, a planted improvement must be detected, and a
planted regression must be detected. If this fails, no report is trustworthy.

## Real example: does adding conventions + a skill help Claude Code?

Requirements: [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) installed and logged in (`claude` on PATH).

```bash
hev evaluate \
  --suite examples/suite \
  --baseline examples/harnesses/baseline \
  --candidate examples/harnesses/candidate \
  --trials 3
```

- **Baseline**: a minimal `AGENTS.md`.
- **Candidate**: `AGENTS.md` with the team conventions + a workflow, plus a `money-arithmetic` skill.
- **Suite** (`examples/suite`): 3 tasks on a small cart library: a bug fix, a feature
  with business rules, and an API addition. Each has hidden acceptance tests and a rubric.

This is 18 agent runs (2 harnesses × 3 tasks × 3 trials); the report shows what it cost. The report
is written to `runs/shop/report__baseline__vs__candidate-conventions-skill/report.md`.
Exit code: `0` positive/neutral, `1` negative, `2` cost trade-off, `3` inconclusive,
so it can gate a harness PR in CI.

> ⚠️ The example harnesses pass `--dangerously-skip-permissions` because headless runs
> cannot answer permission prompts. Run it in a container/VM, or replace the flag in
> `harness.toml` with a narrower `--allowedTools` list.

The requirements judge uses `ANTHROPIC_API_KEY` if set, otherwise the `claude` CLI,
otherwise it is skipped (the report says so). Use `--judge-samples 3` to measure judge noise.

## Concepts

| Concept | What it is | Where |
|---|---|---|
| **Harness** | Everything the team iterates on: agent CLI, model, CLI args, prompt prefix, and an `overlay/` directory (AGENTS.md, CLAUDE.md, `.claude/skills`, `.mcp.json`, hooks…) copied onto the repo before the agent starts. | `harness.toml` + `overlay/` |
| **Task** | A frozen repo snapshot + a business request + **hidden** acceptance tests + a rubric of business requirements. | `tasks/<id>/task.toml` |
| **Suite** | A set of tasks + the team's **conventions** as checkable rules. | `suite.toml` |
| **Trial** | One agent run of one harness on one task in an isolated git workspace. Fully recorded. | `runs/<suite>/<harness>/<task>/trial-N/` |
| **Scorecard** | Per trial: resolved, hidden-test pass rate, conventions, requirements, cost, tokens, time. | `result.json` |
| **Verdict** | Paired, per-task comparison with hierarchical bootstrap CIs, classified against practical thresholds. | `report.md` / `report.json` |

## How a trial is graded

1. **Correctness.** The hidden tests are copied in **after** the agent finishes (it can never
   see or edit them). `resolved` = all hidden tests pass **and** the repo's own suite (including
   tests the agent wrote) is green.
2. **Conventions.** Regex/"must-change" rules from `suite.toml`, applied **only to lines the
   agent added**, so pre-existing debt is never blamed on the harness.
3. **Business requirements.** A blind LLM judge checks the diff against binary rubric
   criteria. It never sees the harness name and runs in an empty dir, so a candidate's
   CLAUDE.md cannot sway it.
4. **Cost.** `total_cost_usd`, tokens and turns from the agent's JSON output.

A run that changes nothing scores 0 on every quality axis. A crashed or timed-out run counts
as a failure and is never dropped, since dropping failures would flatter a flaky harness.

## Reading the verdict

Per metric: `better`/`worse` (95% CI excludes 0 **and** the effect exceeds a practical
threshold), `no meaningful change` (whole CI inside the threshold), or `inconclusive`.
Then:

- any quality metric **worse** → `NEGATIVE`
- some quality **better**, none worse → `POSITIVE` (or `POSITIVE_WITH_COST_TRADEOFF` if cost rose
  more than `--max-cost-increase`, default +25%)
- quality unchanged → `POSITIVE` if cheaper, `NEGATIVE` if costlier, else `NEUTRAL`
- otherwise → `INCONCLUSIVE` (add tasks or trials)

## Using it on your own team

1. **Tasks.** Take 10–30 recently merged PRs. For each, check out the parent commit as the
   `repo`, turn the ticket into the `prompt`, and use the PR's tests as `hidden_tests` (plus a few
   extra edge cases). Write 3–7 binary rubric items from the ticket.
2. **Conventions.** Encode your review checklist as rules in `suite.toml`.
3. **Harnesses.** `baseline` = what's on main today. `candidate` = the proposed change.
   Change **one thing** per candidate.
4. **Run.** `hev evaluate …`. Baseline results are cached by content hash and reused across
   candidates; they re-run automatically if the harness or task changes (`--fresh` forces it).

Other agents: `agent = "codex"` (best effort; parses `codex exec --json` usage) or
`agent = "command"` with `command = ["opencode", "run", "{prompt}"]` for any CLI.

## Layout

```
harness_eval/   config · workspace (git isolation) · agents (adapters) · graders · judge
                runner (trials, cache) · compare (bootstrap, verdict) · report · cli
examples/       repos/shop · suite (3 tasks) · harnesses (baseline, candidate) · selftest
tests/          unit tests + selftest
docs/           ONE_PAGER.md · process/ (how this was built with an agent)
```
