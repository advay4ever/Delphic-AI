import app as app_module
from ai.work_checker import (
    check_math_work,
    extract_math_steps,
    looks_like_work_check_request,
)


def test_finds_the_first_arithmetic_mistake():
    result = check_math_work(
        """Check my work:
        2x + 3 = 11
        2x = 11 - 3
        2x = 7
        x = 3.5"""
    )

    assert result is not None
    assert result.status == "incorrect"
    assert result.current_step_number == 3
    assert "2 x = 7" in result.current_step
    assert "solution set" in result.reason


def test_accepts_equivalent_linear_equation_steps():
    result = check_math_work(
        """2x + 3 = 11
        2x = 8
        x = 4"""
    )

    assert result is not None
    assert result.status == "correct"
    assert result.checked_transitions == 2


def test_checks_fraction_steps():
    result = check_math_work(
        """x/2 + 3 = 7
        x/2 = 4
        x = 8"""
    )

    assert result is not None
    assert result.status == "correct"


def test_treats_exact_decimals_and_equivalent_fractions_as_equal():
    decimal_result = check_math_work("0.1x = 0.3\nx = 3")
    fraction_result = check_math_work("2x = 1\nx = 0.5")

    assert decimal_result is not None
    assert decimal_result.status == "correct"
    assert fraction_result is not None
    assert fraction_result.status == "correct"


def test_checks_common_copied_latex_and_superscripts():
    latex_result = check_math_work(
        r"""\(\frac{x}{2} + 3 = 7\)
        \(\frac{x}{2} = 4\)
        \(x = 8\)"""
    )
    superscript_result = check_math_work("x² = 16\nx = 4")

    assert latex_result is not None
    assert latex_result.status == "correct"
    assert superscript_result is not None
    assert superscript_result.status == "incorrect"


def test_detects_a_power_step_that_adds_an_extra_solution():
    result = check_math_work("""x = 2
    x^2 = 4""")

    assert result is not None
    assert result.status == "incorrect"
    assert result.current_step_number == 2


def test_checks_a_correct_derivative_step():
    result = check_math_work("""f(x) = x^3 + 2x
    f'(x) = 3x^2 + 2""")

    assert result is not None
    assert result.status == "correct"


def test_finds_an_incorrect_derivative_step():
    result = check_math_work("""f(x) = x^3 + 2x
    f'(x) = 3x + 2""")

    assert result is not None
    assert result.status == "incorrect"
    assert "3 x^{2} + 2" in result.reason


def test_checks_one_answer_against_the_previous_problem():
    result = check_math_work(
        "I got x = 5, is this right?",
        [{"role": "user", "content": "Solve 2x + 3 = 11"}],
    )

    assert result is not None
    assert result.status == "incorrect"
    assert result.current_step_number == 1
    assert "2 x + 3 = 11" in result.previous_step


def test_accepts_one_correct_answer_against_the_previous_problem():
    result = check_math_work(
        "My answer: x = 4",
        [{"role": "assistant", "content": "Try this problem: 2x + 3 = 11"}],
    )

    assert result is not None
    assert result.status == "correct"


def test_unsupported_multivariable_work_falls_back_safely():
    assert check_math_work("""x + y = 5
    x = 5 - y""") is None


def test_code_like_input_is_not_parsed_as_math():
    assert extract_math_steps("Check my work: __import__(os) = 1") == []


def test_work_check_intent_detects_words_or_several_steps():
    assert looks_like_work_check_request("Is this right: x = 4")
    assert looks_like_work_check_request("2x + 3 = 11\n2x = 8")
    assert not looks_like_work_check_request("Solve 2x + 3 = 11")


def test_arrow_separated_work_is_checked_in_order():
    result = check_math_work("2x + 3 = 11 -> 2x = 8 -> x = 4")

    assert result is not None
    assert result.status == "correct"


def test_extreme_exponents_and_nonfinite_expressions_are_not_checked():
    assert check_math_work("x = 2\nx^999999 = 4") is None
    assert check_math_work("x/0 = 1\nx = 1") is None


def test_two_false_number_statements_are_not_called_correct():
    result = check_math_work("2 + 3 = 6\n5 = 6")

    assert result is not None
    assert result.status == "incorrect"


def test_one_unsupported_equation_prevents_a_correct_verdict():
    assert check_math_work("""2x + 3 = 11
    x + y = 5
    x = 4""") is None


def test_follow_up_check_detects_a_copied_original_equation_error():
    result = check_math_work(
        """2x + 3 = 12
        2x = 9
        x = 4.5""",
        [{"role": "user", "content": "Solve 2x + 3 = 11"}],
        compare_to_reference=True,
    )

    assert result is not None
    assert result.status == "incorrect"
    assert result.current_step_number == 1


def test_verified_result_is_added_to_the_tutor_prompt(monkeypatch):
    student_message = "I got x = 5, is this right?"
    monkeypatch.setattr(
        app_module,
        "load_messages",
        lambda _session_id: [
            {"role": "user", "content": "Solve 2x + 3 = 11"},
            {"role": "assistant", "content": "Try solving it."},
            {"role": "user", "content": student_message},
        ],
    )
    monkeypatch.setattr(app_module, "increment_question_count", lambda _session_id: 1)
    monkeypatch.setattr(app_module, "add_topic", lambda *_args: None)
    monkeypatch.setattr(app_module, "get_topics", lambda _session_id: [])

    messages = app_module._build_messages_for_ai(
        "work-check-session",
        student_message,
        hint_mode=False,
        check_mode=False,
    )
    system_text = "\n".join(
        message["content"] for message in messages if message["role"] == "system"
    )

    assert "VERIFIED LOCAL WORK CHECK" in system_text
    assert "student step 1" in system_text
    assert "first incorrect transition" in system_text
    assert "For this work-checking response" in system_text
    assert "Structure this new-question response" not in system_text


def test_first_message_with_work_uses_the_work_check_response_shape(monkeypatch):
    student_message = "Check my work:\n2x + 3 = 11\n2x = 7"
    monkeypatch.setattr(
        app_module,
        "load_messages",
        lambda _session_id: [{"role": "user", "content": student_message}],
    )
    monkeypatch.setattr(app_module, "increment_question_count", lambda _session_id: 1)
    monkeypatch.setattr(app_module, "add_topic", lambda *_args: None)
    monkeypatch.setattr(app_module, "get_topics", lambda _session_id: [])

    messages = app_module._build_messages_for_ai(
        "first-work-check",
        student_message,
        hint_mode=False,
        check_mode=False,
    )
    system_text = "\n".join(
        message["content"] for message in messages if message["role"] == "system"
    )

    assert "VERIFIED LOCAL WORK CHECK" in system_text
    assert "WORK CHECKING MODE IS ACTIVE" in system_text
    assert "For this work-checking response" in system_text
    assert "Structure this new-question response" not in system_text


def test_work_check_response_shape_wins_over_practice_mode(monkeypatch):
    student_message = "Check my work:\n2x + 3 = 11\n2x = 7"
    monkeypatch.setattr(
        app_module,
        "load_messages",
        lambda _session_id: [{"role": "user", "content": student_message}],
    )
    monkeypatch.setattr(app_module, "increment_question_count", lambda _session_id: 1)
    monkeypatch.setattr(app_module, "add_topic", lambda *_args: None)
    monkeypatch.setattr(app_module, "get_topics", lambda _session_id: [])

    messages = app_module._build_messages_for_ai(
        "work-check-over-practice",
        student_message,
        hint_mode=False,
        check_mode=False,
        practice_mode=True,
    )
    system_text = "\n".join(
        message["content"] for message in messages if message["role"] == "system"
    )

    assert "For this work-checking response" in system_text
    assert "For this practice response" not in system_text
