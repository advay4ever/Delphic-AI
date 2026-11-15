"""Math input must never execute Python, including model-extracted equations."""

import pytest
import ast

import app as app_module
import ai.detector as detector
import ai.safe_math as safe_math
from ai.math_tools import (
    differentiate, factor_expression, integrate_expr, simplify_expression, solve_equation,
)
from ai.service import AIResponse, AIStreamEvent


TOOLS = [solve_equation, simplify_expression, differentiate, integrate_expr, factor_expression]
PRINT_PROBE = "__import__('builtins').__dict__['print']('MATH_SECURITY_SENTINEL')"


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("expression", [PRINT_PROBE, PRINT_PROBE + " = 1"])
def test_math_tools_reject_executable_input_without_side_effects(tool, expression, capsys):
    result = tool(expression)
    assert "MATH_SECURITY_SENTINEL" not in capsys.readouterr().out
    assert result["success"] is False


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("expression", [
    "x.__class__", "x[0]", "(lambda: 7)()", "[x for x in (1, 2)]",
    "Symbol('x')", "x if True else 1", "x; 2", "print(2)", "x := 1",
])
def test_only_math_syntax_is_accepted(tool, expression):
    result = tool(expression)
    assert result["success"] is False


@pytest.mark.parametrize("route", ["/ask", "/stream"])
@pytest.mark.parametrize("prefix", ["Solve", "Simplify", "Differentiate", "Integrate", "Factor"])
def test_math_request_paths_do_not_execute_input(monkeypatch, capsys, route, prefix):
    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: {"provider": "groq"})
    monkeypatch.setattr(detector, "extract_equation", lambda *args, **kwargs: None)
    monkeypatch.setattr(app_module, "get_math_solution", lambda *args, **kwargs:
                        AIResponse("Mock tutoring response.", 0, "complete"))

    def stream(*args, **kwargs):
        yield AIStreamEvent(text="Mock tutoring response.")
        yield AIStreamEvent(done=True, finish_reason="complete", tokens_used=0)

    monkeypatch.setattr(app_module, "get_math_solution_stream", stream)
    response = app_module.app.test_client().post(route, json={"message": prefix + " " + PRINT_PROBE}, buffered=True)
    assert response.status_code == 200
    assert "MATH_SECURITY_SENTINEL" not in capsys.readouterr().out
    assert b"SymPy verified answer" not in response.data


@pytest.mark.parametrize("extracted", [PRINT_PROBE, PRINT_PROBE + " = 1"])
def test_model_extraction_is_not_a_trusted_execution_path(monkeypatch, extracted, capsys):
    monkeypatch.setattr(detector, "extract_equation", lambda *args, **kwargs: extracted)
    assert detector.detect_and_solve("A rectangle has sides of eight and three. Find its area.") is None
    assert "MATH_SECURITY_SENTINEL" not in capsys.readouterr().out


@pytest.mark.parametrize("route", ["/ask", "/stream"])
@pytest.mark.parametrize("extracted", [PRINT_PROBE, PRINT_PROBE + " = 1"])
def test_request_extraction_fallback_rejects_model_code(monkeypatch, capsys, route, extracted):
    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: {"provider": "groq"})
    monkeypatch.setattr(detector, "extract_equation", lambda *args, **kwargs: extracted)
    captured = []

    def answer(messages, **kwargs):
        captured.extend(messages)
        return AIResponse("Mock response.", 0, "complete")

    def stream(messages, **kwargs):
        captured.extend(messages)
        yield AIStreamEvent(text="Mock response.")
        yield AIStreamEvent(done=True, finish_reason="complete", tokens_used=0)

    monkeypatch.setattr(app_module, "get_math_solution", answer)
    monkeypatch.setattr(app_module, "get_math_solution_stream", stream)
    response = app_module.app.test_client().post(route, json={"message": "A rectangle has sides eight and three. What is its area?"}, buffered=True)
    assert response.status_code == 200
    assert "MATH_SECURITY_SENTINEL" not in capsys.readouterr().out
    assert not any("SymPy computed the exact answer" in message["content"] for message in captured)


def test_valid_model_extracted_equation_remains_supported(monkeypatch):
    monkeypatch.setattr(detector, "extract_equation", lambda *args, **kwargs: "3*x + 7 = 22")
    result = detector.detect_and_solve("A word problem needing extraction.")
    assert "SymPy verified answer" in result and "Solutions: $$5$$" in result


@pytest.mark.parametrize("expression", [
    "x.__class__", "x[0]", "(lambda: 1)()", "[x]", "(x, 1)",
    "x if x else 1", "unknown(x)", "sin(x, evaluate=False)", "True",
])
def test_ast_builder_itself_rejects_code_even_without_text_filters(expression):
    with pytest.raises(safe_math.MathInputError):
        safe_math._build(ast.parse(expression, mode="eval").body, {"x": safe_math.math_symbol("x")})


def test_math_text_transformer_cannot_introduce_executable_ast(monkeypatch, capsys):
    monkeypatch.setattr(safe_math, "stringify_expr", lambda *args, **kwargs: PRINT_PROBE)
    with pytest.raises(safe_math.MathInputError):
        safe_math.parse_math("2 + 2")
    assert "MATH_SECURITY_SENTINEL" not in capsys.readouterr().out


@pytest.mark.parametrize("value", [None, 123, {}, [], True])
@pytest.mark.parametrize("tool", TOOLS)
def test_non_text_input_fails_without_an_interpreter_error(tool, value):
    result = tool(value)
    assert result["success"] is False
    assert "Traceback" not in result["error"]


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("expression", ["x^999999", "9^(9^9)", "x" * 3000,
                                       "1" * 100, "(" * 100 + "x" + ")" * 100])
def test_excessive_input_is_rejected_before_calculation(tool, expression):
    assert tool(expression)["success"] is False


@pytest.mark.parametrize("expression", ["2x + 3 = 11", "(x + 1)(x - 1) = 0", "x^2 + 1 = 0"])
def test_normal_equations_still_work(expression):
    assert solve_equation(expression)["success"] is True


@pytest.mark.parametrize("expression,expected", [
    ("sin(x)^2 + cos(x)^2", "1"), ("sqrt(16) + log(8, 2)", "7"),
    ("1/3 + 1/6", r"\frac{1}{2}"), ("2*pi / pi", "2"),
])
def test_supported_functions_constants_and_fractions(expression, expected):
    result = simplify_expression(expression)
    assert result["success"] is True
    assert result["simplified_latex"] == expected


@pytest.mark.parametrize("expression", ["uv + 2u", "sin x", "cos(x)sin(x)", "1e-3*x", "theta^2", "x^(-2)"])
def test_existing_implicit_notation_and_scientific_numbers(expression):
    assert simplify_expression(expression)["success"] is True


def test_custom_variable_and_calculus_are_preserved():
    assert solve_equation("2y + 3 = 11", variable="y")["solutions"] == ["4"]
    assert differentiate("sin(x)")["derivative_latex"] == r"\cos{\left(x \right)}"
    assert integrate_expr("x^2")["integral_latex"] == r"\frac{x^{3}}{3} + C"
    assert factor_expression("x^2 - 9")["success"] is True
