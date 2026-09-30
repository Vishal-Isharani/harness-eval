from harness_eval.report import build_markdown

CMP = {"baseline": "A", "candidate": "B", "verdict": "NEUTRAL", "reason": "r", "metrics": {},
       "harness_diff": {"added": [], "removed": [], "modified": [], "config": {}}}


def _v(rule, file="src/a.py", line=1, text="x()", message="m"):
    return {"rule": rule, "file": file, "line": line, "text": text, "message": message}


def _rec(task, trial, violations):
    return {"task": task, "trial": trial, "judge": None, "agent": {"error": None},
            "diff": {"empty": False}, "conventions": {"violations": violations},
            "metrics": {"resolved": 1.0, "conventions": 1.0, "requirements": None, "cost_usd": 0.0}}


def _examples(md, harness):
    """Lines of the example section belonging to one harness."""
    section = md.split("### Most frequent rules, with an example")[1].split("\n## ")[0]
    block = section.split(f"**{harness}**")[1].split("\n**")[0]
    return [line for line in block.splitlines() if line.strip()]


def test_duplicates_across_trials_are_grouped_and_lineless_shows_message():
    base = [
        _rec("t1", 0, [_v("no-print", "src/cart.py", 7, "print(x)"),
                       _v("tests", "-", 0, "", "Any change to src/ must add or update tests.")]),
        _rec("t1", 1, [_v("no-print", "src/cart.py", 9, "print(y)")]),
        _rec("t2", 0, [_v("no-print", "src/tax.py", 3, "print(z)")]),
    ]
    lines = _examples(build_markdown(CMP, base, [_rec("t1", 0, [])], trials=2), "A")
    assert lines == [
        "1. `no-print`: 3 violation(s) in 3/3 trials, e.g. `src/cart.py:7`: `print(x)`",
        "2. `tests`: 1 violation(s) in 1/3 trials, e.g. _no file/line_: Any change to src/ must add or update tests.",
    ]


def test_ties_are_ordered_alphabetically():
    base = [_rec("t1", 0, [_v("zeta"), _v("beta"), _v("alpha")])]
    lines = _examples(build_markdown(CMP, base, [_rec("t1", 0, [])], trials=1), "A")
    assert [line.split("`")[1] for line in lines] == ["alpha", "beta", "zeta"]


def test_harness_with_zero_violations_says_so():
    base = [_rec("t1", 0, [_v("no-print")])]
    cand = [_rec("t1", 0, []), _rec("t1", 1, [])]
    md = build_markdown(CMP, base, cand, trials=2)
    assert _examples(md, "B") == ["_No violations._"]
