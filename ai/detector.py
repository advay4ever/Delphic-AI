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
    get_desmos_latex,
)
from ai.service import extract_equation


def detect_and_solve(user_message: str, ai_config: dict | None = None) -> str | None:
    """
    Look at the user's message and try to solve it with SymPy.
    Returns a string with the SymPy result, or None if it can't detect math.
    """
    text = user_message.lower().strip()

    # Try to extract a math expression from the message
    # We look for common patterns like "solve ...", "simplify ...", etc.

    # --- SOLVE ---
    if _matches(text, ["solve", "find x", "find the value", "what is x", "roots of"]):
        expr = _extract_expression(user_message)
        if expr:
            result = solve_equation(expr)
            if result["success"]:
                solutions = ", ".join(result["solutions"])
                return (
                    f"[SymPy verified answer] "
                    f"Equation: $${result['equation_latex']}$$ "
                    f"Solutions: $${solutions}$$"
                )

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

    # --- DIFFERENTIATE ---
    if _matches(text, ["derivative", "differentiate", "d/dx", "derive"]):
        expr = _extract_expression(user_message)
        if expr:
            result = differentiate(expr)
            if result["success"]:
                return (
                    f"[SymPy verified answer] "
                    f"Original: $${result['original_latex']}$$ "
                    f"Derivative: $${result['derivative_latex']}$$"
                )

    # --- INTEGRATE ---
    if _matches(text, ["integral", "integrate", "antiderivative"]):
        expr = _extract_expression(user_message)
        if expr:
            result = integrate_expr(expr)
            if result["success"]:
                return (
                    f"[SymPy verified answer] "
                    f"Original: $${result['original_latex']}$$ "
                    f"Integral: $${result['integral_latex']}$$"
                )

    # --- FALLBACK: Ask AI to extract the equation from a word problem ---
    extracted = extract_equation(user_message, ai_config=ai_config)
    if extracted:
        # Try solving as an equation (if it has '=')
        if "=" in extracted:
            result = solve_equation(extracted)
            if result["success"]:
                solutions = ", ".join(result["solutions"])
                return (
                    f"[SymPy verified answer] "
                    f"Equation: $${result['equation_latex']}$$ "
                    f"Solutions: $${solutions}$$"
                )

        # Otherwise try evaluating it as a simple expression
        result = simplify_expression(extracted)
        if result["success"]:
            return (
                f"[SymPy verified answer] "
                f"Expression: $${result['original_latex']}$$ "
                f"Result: $${result['simplified_latex']}$$"
            )

    return None


def extract_plot_info(user_message: str) -> dict | None:
    """
    Extract plot information for Desmos rendering.
    Returns a dict with type='function' or type='points', plus Desmos-ready data.
    Handles:
      - "plot sin x", "graph y = x^2"
      - bare "y = 2cos(x - pi/2)" with no plot keyword
      - "f(x) = x^2 + 1"
    """
    text = user_message.lower().strip()

    has_plot_keyword = _matches(text, ["plot", "graph", "draw", "sketch", "chart", "show me the graph"])
    has_y_eq = bool(re.match(r"^\s*y\s*=", text)) or bool(re.match(r"^\s*f\s*\(\s*x\s*\)\s*=", text))

    if not has_plot_keyword and not has_y_eq:
        return None

    # --- Points: (x, y) pairs ---
    point_pattern = r"\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)"
    found_points = re.findall(point_pattern, user_message)
    if found_points:
        points = [(float(x), float(y)) for x, y in found_points]
        def _fmt(v):
            return str(int(v)) if v == int(v) else str(v)
        desmos_exprs = [f"({_fmt(x)},{_fmt(y)})" for x, y in points]
        pts_latex = ",\\; ".join(f"({_fmt(x)},\\, {_fmt(y)})" for x, y in points)
        return {
            "type": "points",
            "desmos_exprs": desmos_exprs,
            "equation_latex": pts_latex,
            "raw_expression": ", ".join(desmos_exprs),
        }

    # --- Function ---
    expr = _extract_expression(user_message)
    if not expr:
        return None
    expr = re.sub(r"^(y|f\s*\(\s*x\s*\))\s*=\s*", "", expr.strip(), flags=re.IGNORECASE)
    if not re.search(r"\bx\b|\d", expr, re.IGNORECASE):
        return None
    result = get_desmos_latex(expr)
    if result["success"]:
        return {
            "type": "function",
            "desmos_latex": result["desmos_latex"],
            "equation_latex": result["equation_latex"],
            "raw_expression": expr,
        }
    return None


def _matches(text: str, keywords: list[str]) -> bool:
    """Check if any keyword appears in the text."""
    return any(kw in text for kw in keywords)


def _extract_expression(message: str) -> str | None:
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
        r"d/dx",
        r"f\s*\(\s*x\s*\)\s*=\s*",   # f(x) = ... → strip prefix early (before 2x→2*x regex)
        r"y\s*=\s*",                   # y = ... → strip prefix early
    ]

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
