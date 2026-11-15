import pytest

import app as app_module
from ai.work_checker import check_math_work, MAX_PARSED_STEPS


def test_exactly_twelve_equations_can_be_verified():
    result = check_math_work("\n".join(["2x+3=11", "2x=8"] + ["x=4"] * 10))
    assert result.status == "correct"
    assert result.checked_transitions == MAX_PARSED_STEPS - 1


@pytest.mark.parametrize("last", ["x=99", "x=4", "x+y=4", "x=" + "1+" * 90 + "1"])
def test_unchecked_remainder_cannot_receive_a_complete_verdict(last):
    text = "\n".join(["2x+3=11", "2x=8"] + ["x=4"] * 10 + [last])
    assert check_math_work(text) is None


def test_unsupported_equation_cannot_be_silently_skipped():
    assert check_math_work("x=4\nx=x=99\nx=4") is None


def test_truncated_work_does_not_add_verified_correct_instructions(monkeypatch):
    text = "\n".join(["2x+3=11", "2x=8"] + ["x=4"] * 10 + ["x=99"])
    monkeypatch.setattr(app_module, "load_messages", lambda *_: [{"role": "user", "content": text}])
    monkeypatch.setattr(app_module, "detect_and_solve", lambda *a, **k: None)
    messages = app_module._build_messages_for_ai("completeness-test", text, False, True)
    assert not any("VERIFIED LOCAL WORK CHECK" in str(message) for message in messages)
