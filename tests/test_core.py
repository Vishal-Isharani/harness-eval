from harness_eval.compare import bootstrap, classify
from harness_eval.config import Rule
from harness_eval.graders import added_lines, grade_conventions

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
