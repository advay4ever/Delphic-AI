"""Build bounded SymPy expressions without evaluating student text as Python."""

import ast
from decimal import Decimal, InvalidOperation
import re

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    standard_transformations,
    stringify_expr,
)


MAX_SOURCE_LENGTH = 240
MAX_AST_NODES = 256
MAX_PARENTHESES = 16
MAX_INTEGER_BITS = 8192
MAX_POWER = 32
FUNCTIONS = {
    "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
    "cot": sp.cot, "sec": sp.sec, "csc": sp.csc,
    "asin": sp.asin, "acos": sp.acos, "atan": sp.atan,
    "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh,
    "exp": sp.exp, "log": sp.log, "ln": sp.log,
    "sqrt": sp.sqrt, "abs": sp.Abs, "Abs": sp.Abs,
}
CONSTANTS = {"pi": sp.pi, "E": sp.E, "e": sp.E, "I": sp.I}
TRANSFORMATIONS = standard_transformations + (convert_xor, implicit_multiplication_application)
NUMBER = re.compile(r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")


class MathInputError(ValueError):
    """A student-safe rejection, not a raw interpreter or provider error."""


def math_symbol(name: str) -> sp.Symbol:
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z]|theta", name):
        raise MathInputError("Choose a single-letter variable or theta.")
    return sp.Symbol(name)


def _number(value, *, exact=False):
    text = str(value)
    if len(text) > 32 or not NUMBER.fullmatch(text):
        raise MathInputError("Use a smaller finite number.")
    try:
        number = Decimal(text)
    except InvalidOperation:
        raise MathInputError("Use a smaller finite number.") from None
    if not number.is_finite() or (number and not -100 <= number.adjusted() <= 12):
        raise MathInputError("Use a smaller finite number.")
    if exact:
        return sp.Rational(text)
    return sp.Float(text) if any(mark in text for mark in ".eE") else sp.Integer(text)


def parse_math(source: str, *, exact=False, evaluate=True) -> sp.Expr:
    if not evaluate:
        # Validate numeric growth before preserving the original expression tree.
        parse_math(source, exact=exact)
    if not isinstance(source, str) or not source.strip() or len(source) > MAX_SOURCE_LENGTH:
        raise MathInputError("Use a math expression of 1 to 240 characters.")
    source = source.strip().replace("\u2212", "-").replace("\u00d7", "*").replace("\u00f7", "/")
    source = source.replace("\u00b2", "^2").replace("\u00b3", "^3")
    if (not re.fullmatch(r"[0-9A-Za-z+*/^().,\s-]+", source)
            or source.count("(") > MAX_PARENTHESES):
        raise MathInputError("Use only numbers, variables, supported math functions, and arithmetic symbols.")
    names = set(re.findall(r"[A-Za-z]+", source))
    for name in names:
        if (name not in FUNCTIONS and name not in CONSTANTS and name != "theta"
                and not re.fullmatch(r"[A-Za-z]{1,3}", name)):
            raise MathInputError("That name or function is not supported in a local calculation.")
    symbols = {name: math_symbol(name) for name in names
               if re.fullmatch(r"[A-Za-z]|theta", name) and name not in CONSTANTS}
    namespace = {**FUNCTIONS, **CONSTANTS, **symbols}
    constructors = {"Integer": sp.Integer, "Float": sp.Float, "Symbol": sp.Symbol}
    try:
        # SymPy supplies its established math-notation transformations, not eval.
        transformed = stringify_expr(source, dict(namespace), dict(constructors), TRANSFORMATIONS)
        tree = ast.parse(transformed, mode="eval")
        if sum(1 for _ in ast.walk(tree)) > MAX_AST_NODES:
            raise MathInputError("That expression is too complex for a local calculation.")
        expression = _build(tree.body, namespace, exact=exact, evaluate=evaluate)
    except MathInputError:
        raise
    except (SyntaxError, TypeError, ValueError, KeyError, RecursionError):
        raise MathInputError("Use a supported math expression with balanced parentheses.") from None
    if not isinstance(expression, sp.Expr) or expression.has(sp.nan, sp.zoo, sp.oo, -sp.oo):
        raise MathInputError("That expression does not have a finite defined value.")
    return expression


def _build(node, namespace, *, exact=False, evaluate=True):
    if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
        return _number(node.value, exact=exact)
    if isinstance(node, ast.Name) and node.id in namespace and node.id not in FUNCTIONS:
        return namespace[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        operand = _build(node.operand, namespace, exact=exact, evaluate=evaluate)
        return operand if isinstance(node.op, ast.UAdd) else sp.Mul(-1, operand, evaluate=evaluate)
    if isinstance(node, ast.BinOp):
        left = _build(node.left, namespace, exact=exact, evaluate=evaluate)
        right = _build(node.right, namespace, exact=exact, evaluate=evaluate)
        if isinstance(node.op, ast.Add):
            result = sp.Add(left, right, evaluate=evaluate)
        elif isinstance(node.op, ast.Sub):
            result = sp.Add(left, sp.Mul(-1, right, evaluate=evaluate), evaluate=evaluate)
        elif isinstance(node.op, ast.Mult):
            result = sp.Mul(left, right, evaluate=evaluate)
        elif isinstance(node.op, ast.Div):
            result = sp.Mul(left, sp.Pow(right, -1, evaluate=evaluate), evaluate=evaluate)
        elif isinstance(node.op, ast.Pow):
            if right.is_number and (not right.is_real or abs(right) > MAX_POWER):
                raise MathInputError("Use a smaller exponent for a local calculation.")
            if left.is_Rational and right.is_Integer:
                bits = max(abs(int(part)).bit_length() for part in sp.fraction(left))
                if bits * abs(int(right)) > MAX_INTEGER_BITS:
                    raise MathInputError("That power is too large for a local calculation.")
            result = sp.Pow(left, right, evaluate=evaluate)
        else:
            raise MathInputError("That operation is not supported in a local calculation.")
        if result.is_Rational and any(abs(int(part)).bit_length() > MAX_INTEGER_BITS for part in sp.fraction(result)):
            raise MathInputError("That number is too large for a local calculation.")
        return result
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
        name = node.func.id
        if name == "Symbol" and len(node.args) == 1 and isinstance(node.args[0], ast.Constant):
            return math_symbol(node.args[0].value)
        if name in {"Integer", "Float"} and len(node.args) == 1 and isinstance(node.args[0], ast.Constant):
            return _number(node.args[0].value, exact=exact)
        if name in FUNCTIONS and (len(node.args) == 1 or name in {"log", "ln"} and len(node.args) == 2):
            return FUNCTIONS[name](*(_build(argument, namespace, exact=exact, evaluate=evaluate)
                                     for argument in node.args), evaluate=evaluate)
    raise MathInputError("Only supported math expressions are allowed in a local calculation.")
