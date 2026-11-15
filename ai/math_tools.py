"""
Delphic AI - Symbolic math utilities powered by SymPy
"""

import multiprocessing
import sys
import time

import sympy as sp
from sympy.calculus.singularities import singularities
from ai.safe_math import MAX_SOURCE_LENGTH, MathInputError, math_symbol, parse_math


MAX_CALCULATION_SECONDS = 4


def _run_calculation(operation, source, variable=None):
    if not isinstance(source, str) or not source.strip() or len(source) > 2 * MAX_SOURCE_LENGTH + 1:
        return _failure(MathInputError("Use a shorter supported math expression."))
    if variable is not None:
        try:
            math_symbol(variable)
        except MathInputError as error:
            return _failure(error)
    parent = child = process = None
    started = time.monotonic()
    try:
        context = multiprocessing.get_context("spawn")
        parent, child = context.Pipe(duplex=False)
        process = context.Process(target=_calculation_worker,
                                  args=(child, operation, source, variable), daemon=True)
        process.start()
        child.close()
        if parent.poll(max(0, MAX_CALCULATION_SECONDS - (time.monotonic() - started))):
            result = parent.recv()
            if isinstance(result, dict) and type(result.get("success")) is bool:
                return result
            return _failure(MathInputError("The local calculation could not be verified."))
        return {"success": False, "error_code": "timeout",
                "error": "This calculation took too long to verify locally."}
    except (EOFError, OSError, RuntimeError, ValueError):
        return _failure(MathInputError("The local calculation could not be completed safely."))
    finally:
        if process is not None and process.pid is not None:
            if process.is_alive():
                process.terminate()
            process.join(timeout=1)
            if process.is_alive():
                process.kill()
                process.join(timeout=1)
            if not process.is_alive():
                process.close()
        if parent is not None:
            parent.close()
        if child is not None:
            child.close()


def _calculation_worker(connection, operation, source, variable):
    try:
        if sys.platform.startswith("linux"):
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
        functions = {
            "solve": _solve_equation, "simplify": _simplify_expression,
            "differentiate": _differentiate, "integrate": _integrate_expr,
            "factor": _factor_expression,
        }
        function = functions[operation]
        result = function(source, variable) if operation in {"solve", "differentiate", "integrate"} else function(source)
        connection.send(result)
    except Exception as error:
        try:
            connection.send(_failure(error))
        except (OSError, EOFError):
            pass
    finally:
        connection.close()


def _failure(error):
    message = (str(error) if isinstance(error, MathInputError)
               else "I could not calculate that locally. Try a shorter supported math expression.")
    return {"success": False, "error": message}


def _select_variable(expressions, variable):
    if variable is not None:
        return math_symbol(variable)
    symbols = set().union(*(expression.free_symbols for expression in expressions))
    if len(symbols) > 1:
        raise MathInputError("Choose which variable to calculate before verifying this expression.")
    return next(iter(symbols)) if symbols else math_symbol("x")


def solve_equation(equation_str: str, variable: str | None = None) -> dict:
    """Solve an equation symbolically. E.g. '2*x + 3 = 7'."""
    return _run_calculation("solve", equation_str, variable)


def _solve_equation(equation_str, variable):
    try:
        if "=" in equation_str:
            if equation_str.count("=") != 1:
                raise MathInputError("Use one equals sign in an equation.")
            left, right = equation_str.split("=", 1)
            left_expr = parse_math(left, exact=True, evaluate=False)
            right_expr = parse_math(right, exact=True, evaluate=False)
            var = _select_variable((left_expr, right_expr), variable)
        else:
            left_expr = parse_math(equation_str, exact=True, evaluate=False)
            right_expr = sp.Integer(0)
            var = _select_variable((left_expr,), variable)

        if (left_expr.free_symbols | right_expr.free_symbols) - {var}:
            raise MathInputError("Give values for the other variables before verifying a complete solution set.")
        # Keep the submitted sides intact until their excluded values are known.
        equation = sp.Eq(left_expr, right_expr, evaluate=False)
        excluded = singularities(left_expr, var, domain=sp.S.Complexes).union(
            singularities(right_expr, var, domain=sp.S.Complexes)
        )
        solutions = sp.solveset(equation, var, domain=sp.S.Complexes) - excluded
        if solutions.has(sp.ConditionSet):
            raise MathInputError("I could not verify the complete solution set locally.")
        finite = isinstance(solutions, sp.FiniteSet)
        return {
            "success": True,
            "solutions": [sp.latex(s) for s in sp.ordered(solutions)] if finite else [],
            "solution_set_latex": sp.latex(solutions),
            "solution_kind": "empty" if solutions is sp.S.EmptySet else "finite" if finite else "set",
            "domain_latex": sp.latex(sp.S.Complexes - excluded),
            "variable": str(var),
            "equation_latex": sp.latex(equation),
        }
    except Exception as e:
        return _failure(e)


def simplify_expression(expr_str: str) -> dict:
    """Simplify a mathematical expression."""
    return _run_calculation("simplify", expr_str)


def _simplify_expression(expr_str):
    try:
        expr = parse_math(expr_str)
        simplified = sp.simplify(expr)
        return {
            "success": True,
            "original_latex": sp.latex(expr),
            "simplified_latex": sp.latex(simplified),
        }
    except Exception as e:
        return _failure(e)


def differentiate(expr_str: str, variable: str | None = None) -> dict:
    """Compute the derivative of an expression."""
    return _run_calculation("differentiate", expr_str, variable)


def _differentiate(expr_str, variable):
    try:
        expr = parse_math(expr_str, evaluate=False)
        var = _select_variable((expr,), variable)
        derivative = sp.diff(expr, var)
        return {
            "success": True,
            "original_latex": sp.latex(expr),
            "derivative_latex": sp.latex(derivative),
        }
    except Exception as e:
        return _failure(e)


def integrate_expr(expr_str: str, variable: str | None = None) -> dict:
    """Compute the indefinite integral of an expression."""
    return _run_calculation("integrate", expr_str, variable)


def _integrate_expr(expr_str, variable):
    try:
        expr = parse_math(expr_str, evaluate=False)
        var = _select_variable((expr,), variable)
        integral = sp.integrate(expr, var)
        return {
            "success": True,
            "original_latex": sp.latex(expr),
            "integral_latex": sp.latex(integral) + " + C",
        }
    except Exception as e:
        return _failure(e)


def factor_expression(expr_str: str) -> dict:
    """Factor a polynomial expression."""
    return _run_calculation("factor", expr_str)


def _factor_expression(expr_str):
    try:
        expr = parse_math(expr_str)
        factored = sp.factor(expr)
        return {
            "success": True,
            "original_latex": sp.latex(expr),
            "factored_latex": sp.latex(factored),
        }
    except Exception as e:
        return _failure(e)
