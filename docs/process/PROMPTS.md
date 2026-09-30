# Prompts used (in order)

1. **Design.** "Here is the take-home brief. Before writing code, propose the core concepts
   (what is a harness, a task, a trial), how each quality dimension is measured, and how a
   verdict is reached. List the decisions you are least sure about."
2. **Scaffold.** "Implement config loading + git-isolated workspaces + a claude-code adapter.
   Hidden tests must only be copied in after the agent finishes."
3. **Graders.** "Implement functional grading (junit parsing), conventions on added lines only,
   and a blind rubric judge. A no-op diff must score 0."
4. **Stats.** "Implement paired per-task comparison with a hierarchical bootstrap and a
   better/worse/equivalent/inconclusive classification with practical thresholds."
5. **Trust.** "Add a selftest with planted differences: A/A must be NEUTRAL, good-vs-sloppy
   must be detected in both directions. Then show me a rendered report."
6. **Verify.** "Stub the `claude` binary and prove: the overlay is in the agent's cwd, the judge
   runs in an empty dir, and cost/token parsing works."
