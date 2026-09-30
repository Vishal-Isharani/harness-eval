from harness_eval.compare import bootstrap, classify
from harness_eval.config import Rule
from harness_eval.graders import added_lines, grade_conventions
from harness_eval.report import _top_violations, build_markdown

DIFF = """diff --git a/src/shop/cart.py b/src/shop/cart.py
--- a/src/shop/cart.py
+++ b/src/shop/cart.py
@@ -10,3 +10,4 @@ class Cart:
     def a(self) -> int:
-        return 1
+        return round(2.5)
+        print("x")
"""


def test_added_lines_tracks_new_line_numbers():
    lines = added_lines(DIFF)["src/shop/cart.py"]
    assert lines == [(11, '        return round(2.5)'), (12, '        print("x")')]


def test_conventions_only_judge_added_lines_and_require_tests():
    rules = [
        Rule("no-print", "forbid", ["src/*.py"], "m", pattern=r"\bprint\("),
        Rule("no-float", "forbid", ["src/*.py"], "m", pattern=r"\bround\("),
        Rule("no-exec", "forbid", ["src/*.py"], "m", pattern=r"\bexec\("),
        Rule("tests", "require_change", ["tests/*"], "m", when_changed=["src/*"]),
    ]
    res = grade_conventions(rules, DIFF, ["src/shop/cart.py"])
    assert {v["rule"] for v in res["violations"]} == {"no-print", "no-float", "tests"}
    assert res["score"] == 0.25


def test_classify():
    assert classify(0.2, 0.1, 0.3, 0.05, True) == "better"
    assert classify(-0.2, -0.3, -0.1, 0.05, True) == "worse"
    assert classify(0.2, 0.1, 0.3, 0.05, False) == "worse"  # e.g. cost went up
    assert classify(0.0, -0.01, 0.01, 0.05, True) == "equivalent"
    assert classify(0.0, -0.3, 0.3, 0.05, True) == "inconclusive"


def test_bootstrap_identical_is_zero():
    a = {"t1": [1.0, 0.0], "t2": [1.0, 1.0]}
    point, lo, hi, n = bootstrap(a, a, relative=False)
    assert point == 0 and n == 2


def _v(rule, file="src/a.py", line=1, text="x"):
    return {"rule": rule, "file": file, "line": line, "text": text, "message": f"{rule} msg"}


def _rec(task, trial, violations):
    return {"task": task, "trial": trial, "judge": None, "agent": {"error": None},
            "diff": {"empty": False}, "conventions": {"violations": violations},
            "metrics": {"resolved": 1.0, "conventions": 1.0, "requirements": None, "cost_usd": 0.0}}


BASE = [
    _rec("t1", 0, [_v("no-print", "src/b.py", 9, "print(y)"), _v("no-print", "src/a.py", 3, "print(x)"),
                   _v("tests", "-", 0, ""), _v("no-float", text="1.5")]),
    _rec("t1", 1, [_v("no-print"), _v("no-exec", text="exec(`s`)")]),
    _rec("t2", 0, [_v("tests", "-", 0, ""), _v("no-exec"), _v("tests", "-", 0, "")]),
]


def test_top_violations_ranks_counts_trials_and_picks_located_example():
    top = _top_violations(BASE)
    # no-print 3 in 2 trials, tests 3 in 2 trials -> tie broken by rule id; no-exec 2 beats no-float 1.
    assert [(t["rule"], t["count"], t["trials"]) for t in top] == [
        ("no-print", 3, 2), ("tests", 3, 2), ("no-exec", 2, 2)]
    assert (top[0]["example"]["file"], top[0]["example"]["line"]) == ("src/a.py", 3)
    assert top[1]["example"]["file"] == "-"


def test_report_shows_examples_per_harness():
    cmp = {"baseline": "A", "candidate": "B", "verdict": "NEUTRAL", "reason": "r", "metrics": {},
           "harness_diff": {"added": [], "removed": [], "modified": [], "config": {}}}
    md = build_markdown(cmp, BASE, [_rec("t1", 0, [])], trials=1)
    assert "1. `no-print`: 3 violation(s) in 2/3 trials, e.g. `src/a.py:3`: `print(x)`" in md
    assert "2. `tests`: 3 violation(s) in 2/3 trials, e.g. _no file/line_: tests msg" in md
    assert "3. `no-exec`: 2 violation(s) in 2/3 trials, e.g. `src/a.py:1`: `` exec(`s`) ``" in md
    assert "no-float`: 1" not in md
    assert md.split("**B**")[1].lstrip().startswith("_No violations._")
