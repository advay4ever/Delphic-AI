"""
Unit tests for ai/math_tools.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.math_tools import (
    solve_equation,
    simplify_expression,
    differentiate,
    integrate_expr,
    factor_expression,
)


class TestSolveEquation:
    def test_linear_equation(self):
        result = solve_equation("2*x + 3 = 7")
        assert result["success"] is True
        assert len(result["solutions"]) == 1
        assert "2" in result["solutions"][0]

    def test_quadratic_equation(self):
        result = solve_equation("x**2 - 5*x + 6 = 0")
        assert result["success"] is True
        assert len(result["solutions"]) == 2

    def test_no_solution_info(self):
        result = solve_equation("x**2 + 1 = 0")
        assert result["success"] is True
        # Complex solutions
        assert len(result["solutions"]) == 2

    def test_invalid_input(self):
        result = solve_equation("not a real equation ???")
        assert result["success"] is False


class TestSimplifyExpression:
    def test_basic_simplify(self):
        result = simplify_expression("(x + 1)**2 - x**2")
        assert result["success"] is True

    def test_trig_simplify(self):
        result = simplify_expression("sin(x)**2 + cos(x)**2")
        assert result["success"] is True
        assert result["simplified_latex"] == "1"


class TestDifferentiate:
    def test_power_rule(self):
        result = differentiate("x**3")
        assert result["success"] is True
        assert "3" in result["derivative_latex"]
        assert "x" in result["derivative_latex"]

    def test_trig_derivative(self):
        result = differentiate("sin(x)")
        assert result["success"] is True

    def test_constant(self):
        result = differentiate("5")
        assert result["success"] is True
        assert "0" in result["derivative_latex"]


class TestIntegrate:
    def test_power_rule(self):
        result = integrate_expr("x**2")
        assert result["success"] is True
        assert "C" in result["integral_latex"]

    def test_trig_integral(self):
        result = integrate_expr("cos(x)")
        assert result["success"] is True


class TestFactor:
    def test_quadratic(self):
        result = factor_expression("x**2 + 5*x + 6")
        assert result["success"] is True
        # Should factor into (x+2)(x+3)
        assert "x" in result["factored_latex"]

    def test_difference_of_squares(self):
        result = factor_expression("x**2 - 9")
        assert result["success"] is True
