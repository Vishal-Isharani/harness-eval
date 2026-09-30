from harness_eval.cli import selftest


def test_evaluator_known_answers():
    assert selftest() == 0
