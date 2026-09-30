# Hand checks and agent mistakes

Session: adding "top 3 convention rules with a file:line example" to the report.
Built with Claude Code (Opus 5.5). Full transcript: [`transcript.md`](transcript.md). Times are from the session.

## What I checked

| # | Time | What I checked | How | Result |
|---|---|---|---|---|
| 1 | 4:26 | Claude's explanation of where violations are created, stored and shown | Compared with `graders.py`, `runner.py`, `report.py` | ✔ Correct. It also noticed on its own that `require_change` violations have `file="-"`, `line=0` |
| 2 | 4:27 | Plan covers the edge cases I expected: duplicates across trials, no-line rule, ties, zero violations, markdown breaking | Read the plan against my list | ✔ All covered unprompted. It chose a list over a table so `\|` in code can't break layout. I rejected the first version to question the tie order |
| 3 | 4:29 | How ties are ordered | Asked directly | ✔ Count → trials → rule id. It raised a real gap itself: a tie at the 3rd place is cut silently |
| 4 | 4:31 | Test-first, as required by AGENTS.md | Watched the turn after "Plan approved." | ✖ **It wrote tests and implementation in one turn and never ran the tests red first** |
| 5 | 4:32 | Asked for a failing test | Read its explanation | ⚠ Feature already existed, so it proved "red" by running the new tests against an old copy of `report.py` from HEAD. It was honest about this, but it's a workaround, not test-first |
| 6 | 4:32 | Wording of the empty state | Compared with my request ("No violations") | ✖ Code said "No convention violations". Claude flagged it; after "Fix the test first" it changed the tests first (2 red), then the code (green) ✔ |
| 7 | 4:34 | "Implement it" when it was already implemented | Read its response | ✔ Made no unnecessary changes and showed full pytest (10 passed) and selftest output |
| 8 | 4:36 | Why was `report.py` changed before a failing test? | Asked directly | ✔ It admitted it took "Plan approved." as permission to build immediately, against AGENTS.md, and offered to redo it test-first |
| 9 | 4:39 | Its own list of open risks | Read the summary | ✔ Useful and honest: silent cut at 3rd-place ties, "k/N" includes failed trials, tie-by-trials not tested alone, duplicate test helpers, report not re-rendered after the wording change |

## Where the agent was wrong

1. **Skipped test-first.** "Plan approved." was treated as "implement now". Tests and code landed together, against the AGENTS.md workflow.
2. **Chose the scope itself.** It asked "strict top 3 or add a tie note?" and then picked strict top 3 without waiting for an answer.
3. **Didn't re-verify after the last change.** The sample report wasn't re-rendered after the wording fix; Claude said so itself.

## What I'd change in the harness because of this

- Add to AGENTS.md: *"Plan approval is not permission to implement. After approval, write the tests, run them, and show me they fail before touching src/."*
- Add to AGENTS.md: *"If you asked me a question, wait for the answer before acting."*

## Finding about the tool itself: a result I didn't trust

In Claude's real report, the baseline's most frequent convention violation was `no-true-division` at
`src/shop/cart.py:62`:
`return sum(int(item.subtotal_cents() * TAX_RATE_BPS / 10000) for item in self.items)`.
The code looked familiar: it is the repo's **original** tax line, not something the agent wrote.

| # | What I checked | How | Result |
|---|---|---|---|
| 10 | Was the flagged line new code? | `grep -n "TAX_RATE_BPS / 10000" runs/shop/baseline/discount-codes/trial-0/diff.patch` | ✖ **False positive.** Line 68 removes it (`-`) and line 70 re-adds it (`+`) with more indentation. The agent only moved existing code into a new block |

**Why it happened:** hev grades conventions on lines the agent *added*, to avoid blaming a harness for
pre-existing code. But git shows a moved or re-indented line as removed + added, so the old line was
counted as new work by the baseline agent.

**Impact:** at least one of the baseline's two `no-true-division` violations (the one I checked, trial-0)
was caused by the tool, not the harness. The candidate had zero violations, so the candidate's
advantage on conventions was overstated. The trial-1 violation (`cart.py:54`) has the same rule and
code but I haven't checked its diff yet.

**Fix:** ignore an added line when the same line (ignoring whitespace) was removed in the same file,
then re-grade the saved `diff.patch` files so no agent runs need repeating.

## Follow-ups (not done)

- Exclude moved/re-indented lines from convention grading, and re-grade cached runs.
- Check the trial-1 `no-true-division` violation the same way.
- Show a note when a 4th rule ties for 3rd place.
- Add a test for the tie broken by trial count.
- Merge the duplicated test helpers in `test_core.py` and `test_report.py`.