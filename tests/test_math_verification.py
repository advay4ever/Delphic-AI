import pytest

import ai.detector as detector
from ai.math_tools import differentiate, integrate_expr, solve_equation


@pytest.mark.parametrize("variable", ["x", "y", "t", "theta"])
def test_solver_infers_the_only_unknown(variable):
    assert solve_equation(f"2{variable} + 3 = 7")["solutions"] == ["2"]


def test_calculus_infers_variables_and_respects_explicit_variable():
    assert differentiate("y^2")["derivative_latex"] == "2 y"
    assert integrate_expr("t")["integral_latex"] == r"\frac{t^{2}}{2} + C"
    assert differentiate("y^2", variable="x")["derivative_latex"] == "0"


def test_calculus_keeps_the_original_variable_after_cancellation():
    assert integrate_expr("y/y")["integral_latex"] == "y + C"
    assert differentiate("x/x+y")["success"] is False


@pytest.mark.parametrize("tool,expression", [
    (solve_equation, "x+y=2"), (differentiate, "x*y"), (integrate_expr, "x*y"),
])
def test_ambiguous_variables_are_not_verified(tool, expression):
    assert tool(expression)["success"] is False


@pytest.mark.parametrize("prompt,expected", [
    ("Solve 2y + 3 = 7", "Solutions: $$2$$"),
    ("Solve y = 2", "Solutions: $$2$$"),
    ("Differentiate y^2", "Derivative: $$2 y$$"),
    ("Differentiate x*y with respect to y", "Derivative: $$x$$"),
    ("d/dy y^2", "Derivative: $$2 y$$"),
    ("Integrate t", r"\frac{t^{2}}{2} + C"),
])
def test_detector_uses_the_intended_variable(monkeypatch, prompt, expected):
    monkeypatch.setattr(detector, "extract_equation", lambda *args, **kwargs: None)
    assert expected in detector.detect_and_solve(prompt)


def test_ambiguous_question_does_not_get_verified_context(monkeypatch):
    monkeypatch.setattr(detector, "extract_equation", lambda *args, **kwargs: "x*y")
    assert detector.detect_and_solve("Differentiate x*y") is None


def test_periodic_equation_reports_all_integer_branches(monkeypatch):
    result = solve_equation("sin(x)=0")
    assert result["success"] is True
    assert result["solution_kind"] == "set"
    assert r"\mathbb{Z}" in result["solution_set_latex"]
    monkeypatch.setattr(detector, "extract_equation", lambda *args, **kwargs: None)
    context = detector.detect_and_solve("Solve sin(x)=0")
    assert r"\mathbb{Z}" in context
    assert "Solutions: $$0," not in context


def test_identity_preserves_original_denominator_restrictions():
    result = solve_equation("x/x=1")
    assert result["success"] is True
    assert result["solution_kind"] == "set"
    assert r"\setminus" in result["solution_set_latex"]
    assert r"\left\{0\right\}" in result["solution_set_latex"]
    assert "x" in result["equation_latex"]


@pytest.mark.parametrize("expression", ["(x^2-1)/(x-1)=2", "1/(x-1)=1/(x-1)+1", "2=3"])
def test_empty_solution_set_is_explicit(expression):
    result = solve_equation(expression)
    assert result["success"] is True
    assert result["solution_kind"] == "empty"
    assert result["solution_set_latex"] == r"\emptyset"


def test_unrestricted_identity_is_not_confused_with_no_solution():
    result = solve_equation("x=x")
    assert result["solution_kind"] == "set"
    assert result["solution_set_latex"] == r"\mathbb{C}"


def test_uncertain_solution_set_is_not_verified():
    assert solve_equation("cos(x)=x")["success"] is False


def test_parameter_dependent_equation_does_not_overclaim_a_complete_set():
    assert solve_equation("x*y=0", variable="x")["success"] is False


@pytest.mark.parametrize("route", ["/ask", "/stream"])
def test_correct_variable_context_reaches_the_tutor(monkeypatch, route):
    import app as app_module
    from ai.service import AIResponse, AIStreamEvent

    captured = []
    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: {"provider": "groq"})
    monkeypatch.setattr(detector, "extract_equation", lambda *a, **k: None)

    def answer(messages, **kwargs):
        captured.extend(messages)
        return AIResponse("The solution is y = 2.", 0, "complete")

    def stream(messages, **kwargs):
        captured.extend(messages)
        yield AIStreamEvent(text="The solution is y = 2.")
        yield AIStreamEvent(done=True, tokens_used=0, finish_reason="complete")

    monkeypatch.setattr(app_module, "get_math_solution", answer)
    monkeypatch.setattr(app_module, "get_math_solution_stream", stream)
    response = app_module.app.test_client().post(route, json={"message": "Solve 2y + 3 = 7"}, buffered=True)
    assert response.status_code == 200
    verified = [message["content"] for message in captured if "SymPy computed the exact answer" in message["content"]]
    assert len(verified) == 1
    assert "Solutions: $$2$$" in verified[0]
    assert "Variable: y" in verified[0]
