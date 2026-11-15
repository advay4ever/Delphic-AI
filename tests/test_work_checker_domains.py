import pytest

from ai.work_checker import check_math_work


@pytest.mark.parametrize("text", [
    "x^2/x=0\nx=0",
    "(x-1)^2/(x-1)=0\nx=1",
    "x/x=1\nx=x",
    "sqrt(x)=-1\nx=1",
    "log(x)=0\nx=0",
])
def test_restriction_loss_is_not_verified_as_correct(text):
    result = check_math_work(text)
    assert result is not None
    assert result.status == "incorrect"
    assert "Tell the student the checked work is correct" not in result.to_prompt_context()


@pytest.mark.parametrize("text", [
    "x/2=4\nx=8",
    "(x^2-1)/(x-1)=3\nx=2",
    "sqrt(x)=2\nx=4",
    "log(x)=0\nx=1",
    "x/(x-1)=2\nx=2",
    "0.1x=0.3\nx=3",
])
def test_valid_restricted_equations_keep_their_correct_answers(text):
    result = check_math_work(text)
    assert result is not None
    assert result.status == "correct"


def test_restricted_derivative_is_not_overclaimed():
    assert check_math_work("f(x)=x^2/x\nf'(x)=1") is None
    assert check_math_work("f(x)=x\nf'(x)=x/x") is None
