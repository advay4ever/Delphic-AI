"""
Delphic AI - Detects math intent and runs SymPy when appropriate.

This module sits between the user's question and the AI.
It tries to detect what kind of math the user is asking about,
runs SymPy to get the exact answer, and passes that to the AI
so the AI can explain it step by step.
"""

import re
from ai.math_tools import (
    solve_equation,
    simplify_expression,
    differentiate,
    integrate_expr,
    factor_expression,
)
from ai.graphing import GraphingError, build_graph_spec
from ai.service import extract_equation


def detect_and_solve(user_message: str, ai_config: dict | None = None) -> str | None:
    """
    Look at the user's message and try to solve it with SymPy.
    Returns a string with the SymPy result, or None if it can't detect math.
    """
    text = user_message.lower().strip()
    calculation_message, variable = _extract_requested_variable(user_message)

    # Try to extract a math expression from the message
    # We look for common patterns like "solve ...", "simplify ...", etc.

    # --- SOLVE ---
    if _matches(text, ["solve", "find x", "find the value", "what is x", "roots of"]):
        expr = _extract_expression(calculation_message, keep_equation=True)
        if expr:
            result = solve_equation(expr, variable=variable)
            if result["success"]:
                return _solution_context(result)
            if result.get("error_code") == "timeout":
                return None

    # --- FACTOR ---
    if _matches(text, ["factor"]):
        expr = _extract_expression(user_message)
        if expr:
            result = factor_expression(expr)
            if result["success"]:
                return (
                    f"[SymPy verified answer] "
                    f"Original: $${result['original_latex']}$$ "
                    f"Factored: $${result['factored_latex']}$$"
                )
            if result.get("error_code") == "timeout":
                return None

    # --- SIMPLIFY ---
    if _matches(text, ["simplify", "reduce"]):
        expr = _extract_expression(user_message)
        if expr:
            result = simplify_expression(expr)
            if result["success"]:
                return (
                    f"[SymPy verified answer] "
                    f"Original: $${result['original_latex']}$$ "
                    f"Simplified: $${result['simplified_latex']}$$"
                )
            if result.get("error_code") == "timeout":
                return None

    # --- DIFFERENTIATE ---
    if _matches(text, ["derivative", "differentiate", "derive"]) or re.search(r"\bd/d(?:[a-z]|theta)\b", text):
        expr = _extract_expression(calculation_message)
        if expr:
            result = differentiate(expr, variable=variable)
            if result["success"]:
                return (
                    f"[SymPy verified answer] "
                    f"Original: $${result['original_latex']}$$ "
                    f"Derivative: $${result['derivative_latex']}$$"
                )
            return None

    # --- INTEGRATE ---
    if _matches(text, ["integral", "integrate", "antiderivative"]):
        expr = _extract_expression(calculation_message)
        if expr:
            result = integrate_expr(expr, variable=variable)
            if result["success"]:
                return (
                    f"[SymPy verified answer] "
                    f"Original: $${result['original_latex']}$$ "
                    f"Integral: $${result['integral_latex']}$$"
                )
            return None

    # --- FALLBACK: Ask AI to extract the equation from a word problem ---
    extracted = extract_equation(user_message, ai_config=ai_config)
    if extracted:
        # Try solving as an equation (if it has '=')
        if "=" in extracted:
            result = solve_equation(extracted, variable=variable)
            if result["success"]:
                return _solution_context(result)
            return None

        # Otherwise try evaluating it as a simple expression
        result = simplify_expression(extracted)
        if result["success"]:
            return (
                f"[SymPy verified answer] "
                f"Expression: $${result['original_latex']}$$ "
                f"Result: $${result['simplified_latex']}$$"
            )

    return None


def _solution_context(result: dict) -> str:
    solutions = (", ".join(result["solutions"]) if result["solution_kind"] == "finite"
                 else result["solution_set_latex"])
    return (
        f"[SymPy verified answer] Equation: $${result['equation_latex']}$$ "
        f"Solutions: $${solutions}$$ "
        f"Variable: {result['variable']}. Domain (complex numbers with original exclusions): "
        f"$${result['domain_latex']}$$. Apply any real-only restriction requested by the student."
    )


def extract_plot_info(user_message: str) -> dict | None:
    """
    Extract safe, renderer-neutral graph data.

    Kept as a compatibility helper for callers that previously imported this
    function from ai.detector. New code should call build_graph_spec directly
    when it needs the student-friendly error message.
    """
    try:
        return build_graph_spec(user_message)
    except GraphingError:
        return None


def _matches(text: str, keywords: list[str]) -> bool:
    """Check if any keyword appears in the text."""
    return any(kw in text for kw in keywords)


def _extract_requested_variable(message: str) -> tuple[str, str | None]:
    suffix = re.search(
        r"\s+(?:with respect to|for)\s+([A-Za-z]|theta)\s*[?.!]*$",
        message, flags=re.IGNORECASE,
    )
    derivative = re.search(r"\bd/d([A-Za-z]|theta)\b", message)
    if suffix:
        return message[:suffix.start()].rstrip(), suffix.group(1)
    return message, derivative.group(1) if derivative else None


def _extract_expression(message: str, *, keep_equation: bool = False) -> str | None:
    """
    Try to pull out the math expression from a natural language message.
    E.g. "Solve x^2 + 5x + 6 = 0" → "x^2 + 5x + 6 = 0"
    E.g. "What is the derivative of 3x^2 + 2x?" → "3*x**2 + 2*x"
    """
    text = message.strip()

    # Remove common leading phrases
    prefixes = [
        r"(?:can you |please |could you )?(?:solve|factor|simplify|reduce|differentiate|integrate|derive|find the (?:roots?|value|derivative|integral|antiderivative) (?:of|for)?)",
        r"(?:can you |please |could you )?(?:plot|graph|draw|sketch|chart|show me the graph of)",
        r"(?:what is the |the )?(?:derivative|integral|antiderivative) (?:of )?",
        r"what (?:is|are) (?:the )?(?:roots?|solutions?|values?) (?:of|for|to)",
        r"(?:find|compute|calculate|evaluate)",
        r"d/d(?:theta|[a-z])\b",
    ]
    if not keep_equation:
        prefixes.extend([r"f\s*\(\s*(?:theta|[a-z])\s*\)\s*=\s*", r"y\s*=\s*"])

    cleaned = text
    for prefix in prefixes:
        cleaned = re.sub(prefix, "", cleaned, flags=re.IGNORECASE).strip()

    # Remove trailing question marks and periods
    cleaned = cleaned.rstrip("?.! ")

    if not cleaned:
        return None

    # Convert common math notation to SymPy-friendly format
    expr = cleaned
    # x² → x**2
    expr = re.sub(r"(\w)\²", r"\1**2", expr)
    expr = re.sub(r"(\w)\³", r"\1**3", expr)
    # 2x → 2*x (but not inside words)
    expr = re.sub(r"(\d)([a-zA-Z])", r"\1*\2", expr)
    # x( → x*( for implicit multiplication
    expr = re.sub(r"([a-zA-Z])(\()", r"\1*\2", expr)
    # Undo the * for known math functions (sin*( → sin()
    for fn in ["sin", "cos", "tan", "cot", "sec", "csc", "log", "ln", "exp",
               "sqrt", "abs", "asin", "acos", "atan", "sinh", "cosh", "tanh"]:
        expr = expr.replace(f"{fn}*(", f"{fn}(")
    # ^  → **
    expr = expr.replace("^", "**")

    # Convert "sin x" → "sin(x)", "cos 2*x" → "cos(2*x)", etc.
    # Handles cases where student omits parentheses around trig/math functions
    for fn in ["sinh", "cosh", "tanh", "asin", "acos", "atan",
               "sin", "cos", "tan", "cot", "sec", "csc",
               "log", "ln", "exp", "sqrt", "abs"]:
        expr = re.sub(
            rf"\b{fn}\s+(?!\()([^\s,+\-*/^()]+)",
            lambda m, f=fn: f"{f}({m.group(1)})",
            expr
        )

    return expr if expr else None
