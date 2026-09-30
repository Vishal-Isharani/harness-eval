# hev — did that harness change actually help?

`hev` answers one question for whoever maintains a team's coding-agent harness
(AGENTS.md / CLAUDE.md, skills, MCP config, hooks, workflow prompt, model, or the agent itself):

> **Is the agent producing better code after this change, or not?**

It runs the **baseline** and the **candidate** harness on the same suite of real
tasks, several times each. Every run is graded on **correctness, team conventions,
business requirements and cost**. The report ends in a verdict backed by confidence
intervals: `POSITIVE`, `POSITIVE_WITH_COST_TRADEOFF`, `NEGATIVE`, `NEUTRAL` or `INCONCLUSIVE`.

📄 **See a real result first:** [`reports/example-report.md`](reports/example-report.md) —
Claude Code, baseline vs. a candidate that adds team conventions and a skill.

## Quick start (2 minutes, no API key, no agent)

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
git clone <this repo> && cd harness-eval
uv sync
uv run hev selftest
```

`selftest` checks the evaluator itself against known answers:
- an A/A run (identical harnesses) must come out `NEUTRAL`;
- a planted improvement must be detected;
- a planted regression must be detected.

If this fails, no report is trustworthy.

## Real example: does adding conventions + a skill help Claude Code?

Requires [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) installed and logged in (`claude` on PATH).

```bash
uv run hev evaluate \
  --suite examples/suite \
  --baseline examples/harnesses/baseline \
  --candidate examples/harnesses/candidate \
  --trials 3
```

- **Baseline**: a minimal `AGENTS.md`.
- **Candidate**: `AGENTS.md` with the team conventions and a workflow, plus a `money-arithmetic` skill.
- **Suite** (`examples/suite`): 3 tasks on a small cart library: a bug fix, a feature with
  business rules, and an API addition. Each has hidden acceptance tests and a rubric.

That is 18 agent runs (2 harnesses × 3 tasks × 3 trials), and the report shows what it cost. Output:

- Report: `runs/shop/report__baseline__vs__candidate-conventions-skill/report.md` (+ `report.json`)
- Full artefacts per trial: `runs/shop/<harness>/<task>/trial-N/`, containing the prompt, agent
  output, `diff.patch`, test output and `result.json`.

`runs/` is git-ignored because trial workspaces contain nested git repos. Copy reports you want
to keep into `reports/`.

Exit codes let the evaluation gate a harness PR in CI:

| Code | Verdict |
|---|---|
| `0` | positive or neutral |
| `1` | negative |
| `2` | positive with cost trade-off |
| `3` | inconclusive |

> ⚠️ The example harnesses pass `--dangerously-skip-permissions` because headless runs
> cannot answer permission prompts. Run in a container/VM, or replace the flag in
> `harness.toml` with a narrower `--allowedTools` list.

The requirements judge picks its backend automatically:
- `ANTHROPIC_API_KEY` if set;
- otherwise the `claude` CLI;
- otherwise it is skipped, and the report says so.

Force a backend with `--judge api|claude-cli|off`. Use `--judge-samples 3` to measure judge noise.

### Useful options

| Option | Default | Meaning |
|---|---|---|
| `--trials N` | 3 | runs per task per harness |
| `--jobs N` | 2 | parallel trials |
| `--tasks a,b` | all | run a subset of tasks |
| `--max-cost-increase X` | 0.25 | cost increase tolerated for a quality gain (+25%) |
| `--fresh` | off | ignore cached trial results |
| `--out DIR` | `runs` | where artefacts are written |

`uv run hev run --suite … --harness …` runs a single harness. Its results are cached and reused by `evaluate`.

## Concepts

| Concept | What it is | Where |
|---|---|---|
| **Harness** | Everything the team iterates on: agent CLI, model, CLI args, prompt prefix, and an `overlay/` (AGENTS.md, CLAUDE.md, `.claude/skills`, `.mcp.json`, hooks…) copied onto the repo before the agent starts. | `harness.toml` + `overlay/` |
| **Task** | A frozen repo snapshot + a business request + **hidden** acceptance tests + a rubric of business requirements. | `tasks/<id>/task.toml` |
| **Suite** | A set of tasks + the team's **conventions** as checkable rules. | `suite.toml` |
| **Trial** | One agent run of one harness on one task, in an isolated git workspace. Fully recorded. | `runs/<suite>/<harness>/<task>/trial-N/` |
| **Scorecard** | Per trial: resolved, hidden-test pass rate, conventions, requirements, cost, tokens, time. | `result.json` |
| **Verdict** | Paired per-task comparison, hierarchical bootstrap CIs, classified against practical thresholds. | `report.md` / `report.json` |

## How a trial is graded

1. **Correctness.** Hidden tests are copied in **after** the agent finishes, so it can never see
   or edit them. `resolved` means all hidden tests pass **and** the repo's own suite (including
   tests the agent wrote) is green.
2. **Conventions.** Rules from `suite.toml`, applied **only to lines the agent added**, so
   pre-existing debt is never blamed on the harness.
3. **Business requirements.** A blind LLM judge checks the diff against binary rubric criteria.
   It never sees the harness name and runs in an empty directory, so a candidate's CLAUDE.md
   cannot sway it.
4. **Cost.** `total_cost_usd`, tokens and turns, taken from the agent's JSON output.

A run that changes nothing scores 0 on every quality axis. A crashed or timed-out run counts as
a failure and is never dropped, because dropping failures would flatter a flaky harness.

## Reading the verdict

Each metric is classified as:
- **better / worse**: the 95% CI excludes 0 **and** the effect exceeds a practical threshold;
- **no meaningful change**: the whole CI sits inside the threshold;
- **inconclusive**: anything else.

These combine into the verdict:

- any quality metric **worse** → `NEGATIVE`
- some quality metric **better**, none worse → `POSITIVE`
  (`POSITIVE_WITH_COST_TRADEOFF` if cost rose more than `--max-cost-increase`)
- quality unchanged → `POSITIVE` if cheaper, `NEGATIVE` if costlier, otherwise `NEUTRAL`
- otherwise → `INCONCLUSIVE`; add tasks or trials (more tasks narrow the CI faster than more trials)

## Using it on your own team

1. **Tasks.** Take 10–30 recently merged PRs. For each one:
   - use the parent commit as the `repo`;
   - turn the ticket into the `prompt`;
   - use the PR's tests (plus a few edge cases) as `hidden_tests`;
   - write 3–7 binary rubric items from the ticket.
2. **Conventions.** Encode your review checklist as rules in `suite.toml`, either `forbid` (regex
   on added lines) or `require_change` (e.g. "src changed → tests must change").
3. **Harnesses.** `baseline` is what's on main today; `candidate` is the proposed change. Change
   **one thing** per candidate so the result is attributable.
4. **Run.** `uv run hev evaluate …`. Baseline results are cached by content hash and reused
   across candidates. They re-run automatically if the harness or task changes.

Other agents are supported through the `agent` setting in `harness.toml`:
- `agent = "codex"`: best effort; parses `codex exec --json` usage.
- `agent = "command"` with e.g. `command = ["opencode", "run", "{prompt}"]`: works with any CLI.

## Development

```bash
uv run pytest -q tests     # unit tests + selftest
uv run hev selftest
```

Rules for changing the tool, for humans and agents, are in [`AGENTS.md`](AGENTS.md).

## Known limitations

- **Config leakage:** trials do not yet isolate Claude Code from the user's `~/.claude`
  configuration, which is a confounder.
- **Small example suite:** 3 tasks is a smoke test. The report warns when a suite is too small
  to trust small effects.
- **Moved code counts as new:** conventions are graded on added lines, and git shows moved or
  re-indented code as removed + added. So pre-existing code can be blamed on a harness. This
  happened in a real run (see `docs/process/HAND_CHECKS.md`). Rules are also regex-level and can
  misfire, e.g. a `/` inside a comment.
- **Codex adapter:** best effort and not verified end to end.

## Repository layout

```
harness_eval/     config · workspace (git isolation) · agents (adapters) · graders · judge
                  runner (trials, cache) · compare (bootstrap, verdict) · report · cli
examples/         repos/shop · suite (3 tasks) · harnesses (baseline, candidate) · selftest
reports/          committed evaluation reports
tests/            unit tests + selftest
docs/
  ONE_PAGER.md    concepts, hardest decisions, cuts, a result I didn't trust
  process/        AGENTS.md usage, prompts, hand checks, agent session transcript
```