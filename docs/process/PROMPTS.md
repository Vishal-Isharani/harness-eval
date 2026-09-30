# Prompts used

## 1. Initial build

The first version of hev (concepts, CLI, graders, stats, self-test, example suite) was built in a
Claude chat session, starting from the take-home brief. I then ran it locally, reviewed the code,
ran a real evaluation with Claude Code, and adapted it.

## 2. Claude Code session: top convention violations in the report

All prompts from the recorded session, in order and copied exactly from
[`transcript.md`](transcript.md), including my typos. The steps of the feature were planned in advance;
the follow-ups were my reactions to what Claude did.

| # | Time | Mode | Prompt | Why / what happened |
|---|---|---|---|---|
| 1 | 4:26 | Plan | Read AGENTS.md, then harness_eval/graders.py and harness_eval/report.py. Explain where convention violations are created, what fields each violation has, where they are stored, and where the report currently shows them. Don't write any code yet. | Make it explain the code before changing it, so I can check its understanding against the source. Correct, and it noticed the no-line case on its own. |
| 2 | 4:27 | Plan | I want the report to show, for each harness, the 3 most frequent convention rules with one example each: file:line and the offending code, plus how many trials it happened in. Propose a plan: which files change, what the output looks like, and edge cases. Keep it minimal. | Get a plan I can review against my own list of edge cases. It covered all of them; I rejected the first version to question the tie order. |
| 3 | 4:29 | Plan | Three rules are tied at, so how is the order decided? | Follow-up on the ranking. It explained the order and raised a gap itself: a tie at 3rd place is cut silently. |
| 4 | 4:31 | Plan → edit | Plan approved. | ✖ It treated approval as "implement now" and wrote the tests and the code in one turn, without running the tests red first. |
| 5 | 4:32 | Edit | Before implementing, write a test in tests/ that builds fake trial records and checks the new section. Cover: duplicates across trials are grouped, a violation with no line (file "-") shows its message, ties are ordered alphabetically, and a harness with zero violations shows "No violations". Run it and show me it fails. | Enforce test-first. Since the code already existed, it proved "red" against an old copy of report.py. It also flagged that the code said "No convention violations", not "No violations". |
| 6 | 4:32 | Edit | Fix the test first. | Align the wording, test first. It changed the tests (2 red), then the code (green). |
| 7 | 4:34 | Edit | Implement it in report.py. Then run uv run pytest -q tests and uv run hev selftest and show me the full output. | Require real output, not "tests pass". Nothing left to implement; it showed full output: 10 passed, selftest OK. |
| 8 | 4:36 | Any | Why did you updated @harness_eval/report.py | Question a change I hadn't asked for yet. It admitted it skipped test-first after "Plan approved." |
| 9 | 4:39 | Any | Summarize what you changed and which edge cases are covered. Anything you're unsure about? | Close the session with its own list of risks and gaps. |

## What I'd prompt differently next time

- After approving a plan, say it explicitly: *"Plan approved. Write the tests only, run them, and stop."*
  "Plan approved." on its own was read as permission to build.
- Answer the agent's open questions (strict top 3 vs. a tie note) before approving, instead of leaving it to choose.