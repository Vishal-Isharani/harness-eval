# AGENTS.md — building `hev`

You are helping build `hev`, a CLI that tells a harness maintainer whether a change to a
coding-agent harness improved code quality. Read README.md first.

## Non-negotiables
- **The evaluator must be more trustworthy than the thing it evaluates.** Any change to grading,
  stats or verdict logic must keep `hev selftest` passing (A/A → NEUTRAL, planted improvement →
  POSITIVE*, planted regression → NEGATIVE). If you change the verdict rules, add a selftest case.
- Hidden tests are copied into the workspace only after the agent has finished. Never expose them earlier.
- Failed/crashed/timed-out trials are scored as failures. Never drop them.
- Conventions are evaluated on ADDED lines only.
- The LLM judge must stay blind (no harness name, empty cwd).
- Zero runtime dependencies beyond the stdlib and pytest. Python 3.11+.

## Workflow
1. Before editing, state which concept (Harness/Task/Suite/Trial/Scorecard/Verdict) you are touching.
2. Write or update a test in `tests/` first.
3. Run `python -m pytest -q tests` and `hev selftest`. Paste the output. Do not claim success without it.
4. When you change the report, run an evaluation and read the rendered `report.md`, then check
   at least one number by hand against the trial's `result.json`.
5. Plan approval is not permission to implement. After approval, write the tests, run them,
   and show they fail before touching harness_eval/.
6. If you asked me a question, wait for the answer before acting.

## Don't
- Don't add a 1-10 "quality score" or blend metrics into one number. Keep dimensions separate.
- Don't invent CLI flags for claude/codex. If unsure, make it configurable via `extra_args`.
- Don't add features that aren't in the current task.
