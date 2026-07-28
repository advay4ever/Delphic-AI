"""
Delphic AI - Symbolic math utilities powered by SymPy
"""

import sympy as sp
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    implicit_multiplication_application,
)

transformations = standard_transformations + (implicit_multiplication_application,)


def solve_equation(equation_str: str, variable: str = "x") -> dict:
    """Solve an equation symbolically. E.g. '2*x + 3 = 7'."""
    try:
        var = sp.Symbol(variable)
        if "=" in equation_str:
            left, right = equation_str.split("=", 1)
            left_expr = parse_expr(left.strip(), transformations=transformations)
            right_expr = parse_expr(right.strip(), transformations=transformations)
            equation = sp.Eq(left_expr, right_expr)
        else:
            expr = parse_expr(equation_str.strip(), transformations=transformations)
            equation = sp.Eq(expr, 0)

        solutions = sp.solve(equation, var)
        latex_solutions = [sp.latex(s) for s in solutions]
        return {
            "success": True,
            "solutions": latex_solutions,
            "equation_latex": sp.latex(equation),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def simplify_expression(expr_str: str) -> dict:
    """Simplify a mathematical expression."""
    try:
        expr = parse_expr(expr_str.strip(), transformations=transformations)
        simplified = sp.simplify(expr)
        return {
            "success": True,
            "original_latex": sp.latex(expr),
            "simplified_latex": sp.latex(simplified),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def differentiate(expr_str: str, variable: str = "x") -> dict:
    """Compute the derivative of an expression."""
    try:
        var = sp.Symbol(variable)
        expr = parse_expr(expr_str.strip(), transformations=transformations)
        derivative = sp.diff(expr, var)
        return {
            "success": True,
            "original_latex": sp.latex(expr),
            "derivative_latex": sp.latex(derivative),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def integrate_expr(expr_str: str, variable: str = "x") -> dict:
    """Compute the indefinite integral of an expression."""
    try:
        var = sp.Symbol(variable)
        expr = parse_expr(expr_str.strip(), transformations=transformations)
        integral = sp.integrate(expr, var)
        return {
            "success": True,
            "original_latex": sp.latex(expr),
            "integral_latex": sp.latex(integral) + " + C",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def factor_expression(expr_str: str) -> dict:
    """Factor a polynomial expression."""
    try:
        expr = parse_expr(expr_str.strip(), transformations=transformations)
        factored = sp.factor(expr)
        return {
            "success": True,
            "original_latex": sp.latex(expr),
            "factored_latex": sp.latex(factored),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_desmos_latex(expr_str: str) -> dict:
    """
    Parse a SymPy expression and return the LaTeX string for use in Desmos.
    E.g. 'sin(x)' → { desmos_latex: 'y=\\sin\\left(x\\right)', equation_latex: '\\sin\\left(x\\right)' }
    """
    try:
        expr = parse_expr(expr_str.strip(), transformations=transformations)
        eq_latex = sp.latex(expr)
        return {
            "success": True,
            "equation_latex": eq_latex,
            "desmos_latex": f"y={eq_latex}",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
