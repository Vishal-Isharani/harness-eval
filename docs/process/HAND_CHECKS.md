# Hand checks and agent mistakes

| What | How I checked | Result |
|---|---|---|
| Hidden-test pass rates in the report | Recomputed per task from the sloppy solutions: tax 3/4 (banker's rounding fails half-up), discounts 5/7, remove 3/6 → 65% | Matched |
| Convention scores | Counted applicable rules per sloppy solution: 50% / 17% / 50% | Matched |
| "What changed" section | Read the rendered report for sloppy→good | **Wrong**: it said "no difference (A/A)" because the harness diff ignored `solutions`. Fixed + reworded the message. |
| Claude Code reads AGENTS.md | Checked the docs | **Agent assumption was wrong**: Claude Code reads CLAUDE.md. Without `CLAUDE.md` → `@AGENTS.md`, the candidate's conventions would be silently ignored. |
| Shell scripting | Tool output | Agent used bash brace expansion under `sh` twice; created literal `{a,b}` dirs. Caught from error output. |
| Judge blindness | Stub `claude` logged cwd + files for every call | Judge cwd is an empty temp dir ✔ |
| _(add your own from your real Claude Code run)_ | | |
