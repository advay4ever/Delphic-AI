"""Safe, local graph-data generation for Delphic AI."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
import math
import re
from typing import Any

import sympy as sp


MAX_EXPRESSION_LENGTH = 240
MAX_TOKEN_COUNT = 128
MAX_PAREN_DEPTH = 24
MAX_ABS_LITERAL = 1_000_000
MAX_ABS_EXPONENT = 32
MAX_SYMBOLIC_INTEGER_BITS = 4096
MAX_COMBINED_EXPONENT = 1024
MAX_ABS_GRAPH_VALUE = 100_000
TWO_D_SAMPLE_COUNT = 501
THREE_D_GRID_SIZE = 48
IMPLICIT_TWO_D_GRID_SIZE = 96
IMPLICIT_THREE_D_GRID_SIZE = 20
PARAMETRIC_SAMPLE_COUNT = 720
VECTOR_FIELD_GRID_SIZE = 13
MAX_IMPLICIT_3D_TRIANGLES = 30_000
TWO_D_DOMAIN = (-10.0, 10.0)
THREE_D_DOMAIN = (-5.0, 5.0)
TWO_D_MAX_VIEWPORT_SPAN = 24.0
THREE_D_MAX_VIEWPORT_SPAN = 18.0
MAX_3D_SURFACES = 6

_FUNCTIONS = {
    "abs": abs,
    "acos": math.acos,
    "asin": math.asin,
    "atan": math.atan,
    "cos": math.cos,
    "cosh": math.cosh,
    "cot": lambda value: 1 / math.tan(value),
    "csc": lambda value: 1 / math.sin(value),
    "exp": math.exp,
    "log": math.log,
    "sec": lambda value: 1 / math.cos(value),
    "sin": math.sin,
    "sinh": math.sinh,
    "sqrt": math.sqrt,
    "tan": math.tan,
    "tanh": math.tanh,
}
_SYMPY_FUNCTIONS = {
    "abs": sp.Abs,
    "acos": sp.acos,
    "asin": sp.asin,
    "atan": sp.atan,
    "cos": sp.cos,
    "cosh": sp.cosh,
    "cot": sp.cot,
    "csc": sp.csc,
    "exp": sp.exp,
    "log": sp.log,
    "sec": sp.sec,
    "sin": sp.sin,
    "sinh": sp.sinh,
    "sqrt": sp.sqrt,
    "tan": sp.tan,
    "tanh": sp.tanh,
}
_CONSTANTS = {"e": math.e, "pi": math.pi}
_SYMPY_CONSTANTS = {"e": sp.E, "pi": sp.pi}

_COMMAND_PATTERN = re.compile(
    r"^\s*(?:(?:can|could|would)\s+you\s+)?(?:please\s+)?"
    r"(?:plot|graph|draw|sketch|chart)\b"
    r"(?:\s+(?:the\s+)?(?:graph|function))?(?:\s+of)?\s*",
    re.IGNORECASE,
)
_GRAPH_KEYWORD_PATTERN = re.compile(
    r"\b(?:plot|graph|draw|sketch|chart|show\s+me\s+(?:the\s+)?graph)\b",
    re.IGNORECASE,
)
_POINT_PATTERN = re.compile(
    r"\(\s*(-?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[eE][+-]?\d+)?)\s*,\s*"
    r"(-?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[eE][+-]?\d+)?)\s*\)"
)
_TOKEN_PATTERN = re.compile(
    r"(?P<number>(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[eE][+-]?\d+)?)"
    r"|(?P<name>[A-Za-z]+)"
    r"|(?P<operator>[+\-*/^()])"
)
_SUPERSCRIPT_PATTERN = re.compile(r"[\u2070\u00b9\u00b2\u00b3\u2074-\u2079\u207a\u207b]+")
_SUPERSCRIPT_TRANSLATION = str.maketrans({
    "\u2070": "0",
    "\u00b9": "1",
    "\u00b2": "2",
    "\u00b3": "3",
    "\u2074": "4",
    "\u2075": "5",
    "\u2076": "6",
    "\u2077": "7",
    "\u2078": "8",
    "\u2079": "9",
    "\u207a": "+",
    "\u207b": "-",
})


class GraphingError(ValueError):
    """An error that can be safely shown to a student."""


@dataclass(frozen=True)
class Token:
    kind: str
    value: str


@dataclass(frozen=True)
class Node:
    kind: str
    value: str | float | None = None
    left: Node | None = None
    right: Node | None = None


@dataclass(frozen=True)
class GraphRequest:
    kind: str
    source: str = ""
    points: tuple[tuple[float, float], ...] = ()
    surfaces: tuple["SurfaceRequest", ...] = ()


@dataclass(frozen=True)
class SurfaceRequest:
    """One explicit z surface within a student's 3D graph request."""

    source: str
    label: str
    color_index: int = 0


class _MathParser:
    """A deliberately small parser for graph expressions, not Python code."""

    def __init__(self, source: str):
        self.tokens = _tokenize(source)
        self.position = 0
        self.paren_depth = 0

    @property
    def current(self) -> Token:
        return self.tokens[self.position]

    def advance(self) -> Token:
        token = self.current
        self.position += 1
        return token

    def parse(self) -> Node:
        node = self.parse_sum()
        if self.current.kind != "end":
            raise GraphingError("Use a math expression with only supported symbols and functions.")
        return node

    def parse_sum(self) -> Node:
        node = self.parse_product()
        while self.current.value in {"+", "-"}:
            operator = self.advance().value
            node = Node("binary", operator, node, self.parse_product())
        return node

    def parse_product(self) -> Node:
        node = self.parse_unary()
        while True:
            if self.current.value in {"*", "/"}:
                operator = self.advance().value
                node = Node("binary", operator, node, self.parse_unary())
                continue
            if self._starts_primary(self.current):
                node = Node("binary", "*", node, self.parse_unary())
                continue
            return node

    def parse_unary(self) -> Node:
        if self.current.value in {"+", "-"}:
            operator = self.advance().value
            return Node("unary", operator, self.parse_unary())
        return self.parse_power()

    def parse_power(self) -> Node:
        node = self.parse_primary()
        if self.current.value == "^":
            self.advance()
            exponent = self.parse_unary()
            constant_exponent = _constant_value(exponent)
            if constant_exponent is None or abs(constant_exponent) > MAX_ABS_EXPONENT:
                raise GraphingError("Use a smaller numeric exponent when graphing.")
            return Node("binary", "^", node, exponent)
        return node

    def parse_primary(self) -> Node:
        token = self.current

        if token.kind == "number":
            self.advance()
            value = float(token.value)
            if not math.isfinite(value) or abs(value) > MAX_ABS_LITERAL:
                raise GraphingError("Use smaller numbers when graphing.")
            return Node("number", value)

        if token.kind == "name":
            name = self.advance().value.lower()
            if name in _CONSTANTS:
                return Node("constant", name)
            if name in {"x", "y", "z", "t", "theta"}:
                return Node("variable", name)
            if name not in _FUNCTIONS:
                raise GraphingError(f"I do not support {name} in a graph yet.")

            if self.current.value == "(":
                self.advance()
                self.paren_depth += 1
                if self.paren_depth > MAX_PAREN_DEPTH:
                    raise GraphingError("That expression has too many nested parentheses.")
                argument = self.parse_sum()
                if self.current.value != ")":
                    raise GraphingError("Check that every opening parenthesis has a closing parenthesis.")
                self.advance()
                self.paren_depth -= 1
            else:
                argument = self.parse_power()
            return Node("function", name, argument)

        if token.value == "(":
            self.advance()
            self.paren_depth += 1
            if self.paren_depth > MAX_PAREN_DEPTH:
                raise GraphingError("That expression has too many nested parentheses.")
            node = self.parse_sum()
            if self.current.value != ")":
                raise GraphingError("Check that every opening parenthesis has a closing parenthesis.")
            self.advance()
            self.paren_depth -= 1
            return node

        raise GraphingError("Use a math expression such as y = x^2 - 4.")


    @staticmethod
    def _starts_primary(token: Token) -> bool:
        return token.kind in {"number", "name"} or token.value == "("


def _tokenize(source: str) -> list[Token]:
    if not source or len(source) > MAX_EXPRESSION_LENGTH:
        raise GraphingError("Keep a graph equation under 240 characters.")

    tokens: list[Token] = []
    position = 0
    while position < len(source):
        if source[position].isspace():
            position += 1
            continue
        match = _TOKEN_PATTERN.match(source, position)
        if not match:
            raise GraphingError("Use numbers, x/y/z/t, parentheses, and supported math functions.")
        kind = "number" if match.group("number") else "name" if match.group("name") else "operator"
        tokens.append(Token(kind, match.group(0)))
        position = match.end()

        if len(tokens) > MAX_TOKEN_COUNT:
            raise GraphingError("That graph equation is too complex. Try a shorter version.")

    tokens.append(Token("end", ""))
    return tokens


def _normalise_source(source: str) -> str:
    source = source.strip()
    source = (
        source.replace("\u2212", "-")
        .replace("\u00d7", "*")
        .replace("\u00f7", "/")
        .replace("\u03c0", "pi")
        .replace("\u03b8", "theta")
        .replace("\u221a", "sqrt ")
    )
    source = source.replace("**", "^")

    def replace_superscript(match: re.Match[str]) -> str:
        return "^" + match.group(0).translate(_SUPERSCRIPT_TRANSLATION)

    source = _SUPERSCRIPT_PATTERN.sub(replace_superscript, source)
    source = re.sub(r"\bln\b", "log", source, flags=re.IGNORECASE)
    # Accept compact square-root shorthand such as sqrtx^2 from typed or pasted math.
    source = re.sub(r"\bsqrt(?=[xyzt](?:\b|\^))", "sqrt ", source, flags=re.IGNORECASE)
    return source.strip()


def _trim_outer_graph_punctuation(message: str) -> str:
    """Ignore harmless punctuation wrapped around a student's graph request."""
    return message.strip(" \t\r\n,;:!?.\"'`")


def _strip_graph_command(message: str) -> tuple[str, bool]:
    message = _trim_outer_graph_punctuation(message)
    has_keyword = bool(_GRAPH_KEYWORD_PATTERN.search(message))
    return _trim_outer_graph_punctuation(_COMMAND_PATTERN.sub("", message, count=1)), has_keyword


def _extract_points(source: str) -> tuple[tuple[float, float], ...] | None:
    matches = _POINT_PATTERN.findall(source)
    if not matches:
        return None

    remainder = _POINT_PATTERN.sub("", source)
    remainder = re.sub(r"\b(?:points?|are)\b", "", remainder, flags=re.IGNORECASE)
    remainder = remainder.replace(",", "").replace(";", "").replace(":", "").strip()
    if remainder:
        return None

    points = tuple((float(x), float(y)) for x, y in matches)
    if len(points) > 100:
        raise GraphingError("Plot up to 100 points at one time.")
    if any(
        not math.isfinite(value) or abs(value) > MAX_ABS_GRAPH_VALUE
        for point in points
        for value in point
    ):
        raise GraphingError("Use finite point coordinates smaller than 100000.")
    return points


def _split_equation(source: str) -> tuple[str, str] | None:
    """Split one equality without accepting arbitrary comparison syntax."""
    if source.count("=") != 1:
        return None
    left, right = source.split("=", 1)
    left = _normalise_source(left)
    right = _normalise_source(right)
    if not left or not right:
        raise GraphingError("Type an expression on both sides of the equals sign.")
    return left, right


def _has_variable(source: str, variable: str) -> bool:
    return bool(re.search(rf"\b{re.escape(variable)}\b", source, re.IGNORECASE))


def _extract_parametric_components(source: str) -> dict[str, str] | None:
    """Read x=..., y=...[, z=...] components separated by commas or lines."""
    parts = [part.strip() for part in re.split(r"[,;\r\n]+", source) if part.strip()]
    if len(parts) not in {2, 3}:
        return None

    components: dict[str, str] = {}
    for part in parts:
        match = re.fullmatch(r"(?P<axis>[xyz])\s*=\s*(?P<expression>.+)", part, re.IGNORECASE)
        if match is None:
            return None
        axis = match.group("axis").lower()
        if axis in components:
            return None
        components[axis] = _normalise_source(match.group("expression"))

    if set(components) not in ({"x", "y"}, {"x", "y", "z"}):
        return None
    return components


def _is_piecewise_source(source: str) -> bool:
    return ";" in source and bool(re.search(r"\b(?:for|when|if)\b", source, re.IGNORECASE))


def _is_vector_field_source(source: str) -> bool:
    return bool(re.search(r"\b(?:vector\s+field|field)\b.*<.+,.+>", source, re.IGNORECASE | re.DOTALL))


def _is_inequality_source(source: str) -> bool:
    return any(symbol in source for symbol in ("<=", ">=", "\u2264", "\u2265"))


def _is_3d_system_source(source: str) -> bool:
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    return len(lines) >= 2 and any(_has_variable(line, "z") for line in lines)


def _extract_3d_surface_system(source: str) -> tuple[SurfaceRequest, ...] | None:
    """Recognize a short, line-separated system of supported 3D z equations.

    An equation such as z^2 = x^2 + y^2 is represented by two ordinary
    surfaces so the local renderer does not need a general implicit-surface
    engine. This covers familiar double cones while keeping evaluation safe.
    """
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    if not lines:
        return None

    has_squared_z = any(
        re.match(r"^\s*z\s*(?:\^\s*2|\u00b2)\s*=", line, re.IGNORECASE)
        for line in lines
    )
    if len(lines) < 2 and not has_squared_z:
        return None
    if not all(re.match(r"^\s*z\s*(?:=|\^\s*2|\u00b2)", line, re.IGNORECASE) for line in lines):
        return None

    surfaces: list[SurfaceRequest] = []
    for color_index, line in enumerate(lines):
        squared_match = re.match(
            r"^\s*z\s*(?:\^\s*2|\u00b2)\s*=\s*(?P<rhs>.+?)\s*$",
            line,
            re.IGNORECASE,
        )
        explicit_match = re.match(r"^\s*z\s*=\s*(?P<rhs>.+?)\s*$", line, re.IGNORECASE)
        match = squared_match or explicit_match
        if match is None:
            raise GraphingError(
                "For a 3D system, put one z equation on each line, such as z^2 = x^2 + y^2."
            )

        rhs = _normalise_source(match.group("rhs"))
        if not rhs:
            raise GraphingError("Type an equation after each equals sign.")

        if squared_match:
            label = f"z^2 = {rhs}"
            surfaces.extend((
                SurfaceRequest(f"sqrt ({rhs})", f"z = sqrt({rhs})", color_index),
                SurfaceRequest(f"-sqrt ({rhs})", f"z = -sqrt({rhs})", color_index),
            ))
        else:
            surfaces.append(SurfaceRequest(rhs, f"z = {rhs}", color_index))

    if len(surfaces) > MAX_3D_SURFACES:
        raise GraphingError("Graph up to six 3D surfaces at one time.")
    return tuple(surfaces)


def extract_graph_request(message: str) -> GraphRequest | None:
    """Recognize the supported graph forms without parsing arbitrary code."""
    source, has_keyword = _strip_graph_command(message.strip())
    points = _extract_points(source)
    if points is not None:
        return GraphRequest("points_2d", points=points)

    components = _extract_parametric_components(source)
    if components is not None:
        return GraphRequest("curve_3d" if "z" in components else "parametric_2d", source=source)

    if _is_vector_field_source(source):
        return GraphRequest("vector_field_2d", source=source)

    if _is_piecewise_source(source):
        return GraphRequest("piecewise_2d", source=source)

    if _is_inequality_source(source):
        return GraphRequest("inequality_2d", source=source)

    polar_match = re.match(r"^\s*r\s*=\s*(?P<rhs>.+)$", source, re.IGNORECASE)
    if polar_match:
        return GraphRequest("polar_2d", source=_normalise_source(polar_match.group("rhs")))

    if _is_3d_system_source(source):
        return GraphRequest("system_3d", source=source)

    surfaces = _extract_3d_surface_system(source)
    if surfaces is not None:
        return GraphRequest("surface_3d", surfaces=surfaces)

    lhs_match = re.match(r"^\s*(?P<lhs>y|z|f\s*\(\s*x\s*\))\s*=\s*(?P<rhs>.+)$", source, re.IGNORECASE)
    if lhs_match:
        lhs = lhs_match.group("lhs").lower().replace(" ", "")
        rhs = _normalise_source(lhs_match.group("rhs"))
        if not rhs:
            raise GraphingError("Type an equation after the equals sign.")
        kind = "surface_3d" if lhs == "z" else "function_2d"
        return GraphRequest(kind, rhs)

    equation = _split_equation(source)
    if equation is not None:
        left, right = equation
        if _has_variable(f"{left} {right}", "z"):
            return GraphRequest("implicit_3d", source=source)
        if _has_variable(f"{left} {right}", "x") or _has_variable(f"{left} {right}", "y"):
            return GraphRequest("implicit_2d", source=source)

    if has_keyword:
        expression = _normalise_source(source)
        if not expression:
            raise GraphingError("Type an equation to graph, such as y = x^2 - 4.")
        return GraphRequest("function_2d", expression)

    return None


def _constant_value(node: Node) -> float | None:
    try:
        value = _evaluate(node, {})
    except (ArithmeticError, ValueError, ZeroDivisionError):
        return None
    return value if math.isfinite(value) else None


@lru_cache(maxsize=256)
def _rational_constant(node: Node) -> Fraction | None:
    """Preserve an exact rational exponent instead of guessing from a float."""
    if node.kind == "number":
        return Fraction(str(node.value))
    if node.kind == "unary":
        child = _rational_constant(node.left)
        return None if child is None else child if node.value == "+" else -child
    if node.kind != "binary":
        return None
    left, right = _rational_constant(node.left), _rational_constant(node.right)
    if left is None or right is None:
        return None
    try:
        if node.value == "+":
            result = left + right
        elif node.value == "-":
            result = left - right
        elif node.value == "*":
            result = left * right
        elif node.value == "/":
            result = left / right
        elif node.value == "^" and right.denominator == 1 and abs(right) <= MAX_ABS_EXPONENT:
            if max(left.numerator.bit_length(), left.denominator.bit_length()) * abs(right.numerator) > MAX_SYMBOLIC_INTEGER_BITS:
                return None
            result = left ** right.numerator
        else:
            return None
    except (ArithmeticError, ValueError):
        return None
    if max(result.numerator.bit_length(), result.denominator.bit_length()) > MAX_SYMBOLIC_INTEGER_BITS:
        return None
    return result


def _evaluate(node: Node, variables: dict[str, float]) -> float:
    try:
        if node.kind == "number":
            value = float(node.value)
        elif node.kind == "constant":
            value = _CONSTANTS[str(node.value)]
        elif node.kind == "variable":
            value = variables[str(node.value)]
        elif node.kind == "unary":
            child = _evaluate(node.left, variables)
            value = child if node.value == "+" else -child
        elif node.kind == "binary":
            left = _evaluate(node.left, variables)
            right = _evaluate(node.right, variables)
            if node.value == "+":
                value = left + right
            elif node.value == "-":
                value = left - right
            elif node.value == "*":
                value = left * right
            elif node.value == "/":
                value = left / right
            else:
                exponent = _rational_constant(node.right) if left < 0 and not right.is_integer() else None
                if exponent is not None and exponent.denominator % 2 == 1:
                    value = math.pow(-left, right) * (-1 if exponent.numerator % 2 else 1)
                else:
                    value = math.pow(left, right)
        elif node.kind == "function":
            value = _FUNCTIONS[str(node.value)](_evaluate(node.left, variables))
        else:
            raise ValueError("Unknown graph expression node.")
    except (ArithmeticError, ValueError, OverflowError, ZeroDivisionError, KeyError):
        return math.nan

    return float(value) if math.isfinite(value) else math.nan


def _to_sympy(node: Node) -> sp.Expr:
    if node.kind == "number":
        value = float(node.value)
        return sp.Integer(int(value)) if value.is_integer() else sp.Float(value)
    if node.kind == "constant":
        return _SYMPY_CONSTANTS[str(node.value)]
    if node.kind == "variable":
        return sp.Symbol(str(node.value), real=True)
    if node.kind == "unary":
        child = _to_sympy(node.left)
        return child if node.value == "+" else -child
    if node.kind == "binary":
        left = _to_sympy(node.left)
        right = _to_sympy(node.right)
        if node.value == "+":
            result = left + right
        elif node.value == "-":
            result = left - right
        elif node.value == "*":
            result = left * right
        elif node.value == "/":
            result = left / right
        elif node.value == "^":
            if left.is_Rational and right.is_Integer:
                bits = max(abs(int(part)).bit_length() for part in sp.fraction(left))
                if bits * abs(int(right)) > MAX_SYMBOLIC_INTEGER_BITS:
                    raise GraphingError("That nested power is too large to graph. Try a simpler equation.")
            if left.is_Pow and left.exp.is_number and right.is_number:
                if abs(left.exp * right) > MAX_COMBINED_EXPONENT:
                    raise GraphingError("That nested power is too large to graph. Try a simpler equation.")
            # Fractional powers need no exact root extraction for a graph label.
            result = sp.Pow(left, right, evaluate=bool(right.is_Integer))
        else:
            raise GraphingError("That graph operation is not supported.")
        if result.is_Rational and any(abs(int(part)).bit_length() > MAX_SYMBOLIC_INTEGER_BITS
                                      for part in sp.fraction(result)):
            raise GraphingError("That expression produces numbers too large to graph.")
        return result
    if node.kind == "function":
        return _SYMPY_FUNCTIONS[str(node.value)](_to_sympy(node.left), evaluate=False)
    raise ValueError("Unknown graph expression node.")


def parse_graph_expression(source: str, allowed_variables: set[str]) -> tuple[Node, sp.Expr]:
    """Parse only the limited graph language and reject the other variable names."""
    node = _MathParser(_normalise_source(source)).parse()
    variables = _collect_variables(node)
    unsupported = variables - allowed_variables
    if unsupported:
        names = ", ".join(sorted(unsupported))
        raise GraphingError(f"This graph uses {names}, which is not supported here.")
    return node, _to_sympy(node)


def _collect_variables(node: Node) -> set[str]:
    if node.kind == "variable":
        return {str(node.value)}
    variables: set[str] = set()
    if node.left is not None:
        variables.update(_collect_variables(node.left))
    if node.right is not None:
        variables.update(_collect_variables(node.right))
    return variables


def _quantile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _auto_range(
    values: list[float],
    fallback: tuple[float, float],
    max_span: float | None = None,
) -> tuple[float, float]:
    useful = [value for value in values if math.isfinite(value) and abs(value) <= MAX_ABS_GRAPH_VALUE]
    if not useful:
        return fallback

    lower = _quantile(useful, 0.02)
    upper = _quantile(useful, 0.98)
    span = upper - lower
    if span < 0.01:
        lower -= 1.0
        upper += 1.0

    content_span = max_span / 1.24 if max_span is not None else math.inf
    origin_lower, origin_upper = min(lower, 0.0), max(upper, 0.0)
    if origin_upper - origin_lower <= content_span:
        lower, upper = origin_lower, origin_upper
    elif upper - lower > content_span:
        if lower <= 0 <= upper:
            if abs(lower) <= content_span:
                upper = lower + content_span
            elif abs(upper) <= content_span:
                lower = upper - content_span
            else:
                lower = -content_span / 2
                upper = content_span / 2
        elif lower > 0:
            if lower <= content_span / 2:
                lower, upper = 0.0, content_span
            else:
                center = (lower + upper) / 2
                lower, upper = center - content_span / 2, center + content_span / 2
        else:
            if abs(upper) <= content_span / 2:
                lower, upper = -content_span, 0.0
            else:
                center = (lower + upper) / 2
                lower, upper = center - content_span / 2, center + content_span / 2

    span = upper - lower
    padding = max(span * 0.12, 0.5)
    return (
        max(lower - padding, -MAX_ABS_GRAPH_VALUE),
        min(upper + padding, MAX_ABS_GRAPH_VALUE),
    )


def _format_number(value: float) -> float:
    return round(value, 8)


def build_2d_graph_spec(source: str) -> dict[str, Any]:
    node, sympy_expression = parse_graph_expression(source, {"x"})
    x_min, x_max = TWO_D_DOMAIN
    samples: list[tuple[float, float | None]] = []
    finite_values: list[float] = []

    for index in range(TWO_D_SAMPLE_COUNT):
        x_value = x_min + (x_max - x_min) * index / (TWO_D_SAMPLE_COUNT - 1)
        y_value = _evaluate(node, {"x": x_value})
        if math.isfinite(y_value) and abs(y_value) <= MAX_ABS_GRAPH_VALUE:
            samples.append((x_value, y_value))
            finite_values.append(y_value)
        else:
            samples.append((x_value, None))

    y_min, y_max = _auto_range(
        finite_values,
        (-10.0, 10.0),
        max_span=TWO_D_MAX_VIEWPORT_SPAN,
    )
    y_span = max(y_max - y_min, 1.0)
    rendered_min = y_min - y_span
    rendered_max = y_max + y_span
    jump_limit = max(y_span * 1.5, 10.0)

    segments: list[list[list[float]]] = []
    current: list[list[float]] = []
    previous_y: float | None = None
    for x_value, y_value in samples:
        is_visible = y_value is not None and rendered_min <= y_value <= rendered_max
        if not is_visible or (previous_y is not None and abs(y_value - previous_y) > jump_limit):
            if len(current) >= 2:
                segments.append(current)
            current = []
            previous_y = None
            if not is_visible:
                continue

        current.append([_format_number(x_value), _format_number(y_value)])
        previous_y = y_value

    if len(current) >= 2:
        segments.append(current)

    if not segments:
        raise GraphingError("I could not find visible real values for that 2D graph.")

    equation_latex = sp.latex(sympy_expression)
    return {
        "version": 1,
        "kind": "function_2d",
        "equation_latex": equation_latex,
        "raw_expression": f"y = {source}",
        "viewport": {
            "x_min": x_min,
            "x_max": x_max,
            "y_min": y_min,
            "y_max": y_max,
        },
        "series": [{"label": f"y = {source}", "segments": segments}],
    }


def _equation_latex(left: str, right: str, relation: str = "=") -> str:
    _, left_expression = parse_graph_expression(left, {"x", "y", "z", "t", "theta"})
    _, right_expression = parse_graph_expression(right, {"x", "y", "z", "t", "theta"})
    return f"{sp.latex(left_expression)} {relation} {sp.latex(right_expression)}"


def _build_marching_square_segments(
    values: list[list[float | None]],
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
) -> list[list[list[float]]]:
    """Trace a zero contour with bounded marching squares samples."""
    rows = len(values)
    columns = len(values[0]) if rows else 0
    if rows < 2 or columns < 2:
        return []

    def point(row: int, column: int) -> tuple[float, float]:
        return (
            x_min + (x_max - x_min) * column / (columns - 1),
            y_min + (y_max - y_min) * row / (rows - 1),
        )

    def intersection(
        first_point: tuple[float, float],
        first_value: float,
        second_point: tuple[float, float],
        second_value: float,
    ) -> tuple[float, float] | None:
        if not math.isfinite(first_value) or not math.isfinite(second_value):
            return None
        if abs(first_value) < 1e-12 and abs(second_value) < 1e-12:
            return None
        if first_value * second_value > 0:
            return None
        denominator = first_value - second_value
        ratio = 0.5 if abs(denominator) < 1e-12 else first_value / denominator
        ratio = min(max(ratio, 0.0), 1.0)
        return (
            first_point[0] + (second_point[0] - first_point[0]) * ratio,
            first_point[1] + (second_point[1] - first_point[1]) * ratio,
        )

    segments: list[list[list[float]]] = []
    for row in range(rows - 1):
        for column in range(columns - 1):
            corners = [
                (point(row, column), values[row][column]),
                (point(row, column + 1), values[row][column + 1]),
                (point(row + 1, column + 1), values[row + 1][column + 1]),
                (point(row + 1, column), values[row + 1][column]),
            ]
            intersections: list[tuple[float, float]] = []
            for edge in range(4):
                first_point, first_value = corners[edge]
                second_point, second_value = corners[(edge + 1) % 4]
                crossing = intersection(first_point, first_value, second_point, second_value)
                if crossing is not None and crossing not in intersections:
                    intersections.append(crossing)
            if len(intersections) == 2:
                segments.append([
                    [_format_number(intersections[0][0]), _format_number(intersections[0][1])],
                    [_format_number(intersections[1][0]), _format_number(intersections[1][1])],
                ])
            elif len(intersections) == 4:
                for first, second in ((0, 1), (2, 3)):
                    segments.append([
                        [_format_number(intersections[first][0]), _format_number(intersections[first][1])],
                        [_format_number(intersections[second][0]), _format_number(intersections[second][1])],
                    ])
    return segments


def _build_curve_segments(
    samples: list[tuple[float, float] | None],
    jump_limit: float,
) -> list[list[list[float]]]:
    segments: list[list[list[float]]] = []
    current: list[list[float]] = []
    previous: tuple[float, float] | None = None
    for sample in samples:
        if sample is None or (previous is not None and math.dist(previous, sample) > jump_limit):
            if len(current) >= 2:
                segments.append(current)
            current = []
            previous = None
            if sample is None:
                continue
        current.append([_format_number(sample[0]), _format_number(sample[1])])
        previous = sample
    if len(current) >= 2:
        segments.append(current)
    return segments


def build_implicit_2d_graph_spec(source: str) -> dict[str, Any]:
    equation = _split_equation(source)
    if equation is None:
        raise GraphingError("Use an equation such as x^2 + y^2 = 25.")
    left, right = equation
    node, _ = parse_graph_expression(f"({left}) - ({right})", {"x", "y"})
    x_min, x_max = TWO_D_DOMAIN
    y_min, y_max = TWO_D_DOMAIN
    values: list[list[float | None]] = []
    for row in range(IMPLICIT_TWO_D_GRID_SIZE + 1):
        y_value = y_min + (y_max - y_min) * row / IMPLICIT_TWO_D_GRID_SIZE
        value_row: list[float | None] = []
        for column in range(IMPLICIT_TWO_D_GRID_SIZE + 1):
            x_value = x_min + (x_max - x_min) * column / IMPLICIT_TWO_D_GRID_SIZE
            value = _evaluate(node, {"x": x_value, "y": y_value})
            value_row.append(value if math.isfinite(value) else None)
        values.append(value_row)

    segments = _build_marching_square_segments(values, x_min, x_max, y_min, y_max)
    if not segments:
        raise GraphingError("I could not find a visible 2D curve for that equation.")
    curve_points = [point for segment in segments for point in segment]
    view_x_min, view_x_max = _auto_range(
        [point[0] for point in curve_points],
        (x_min, x_max),
        TWO_D_MAX_VIEWPORT_SPAN,
    )
    view_y_min, view_y_max = _auto_range(
        [point[1] for point in curve_points],
        (y_min, y_max),
        TWO_D_MAX_VIEWPORT_SPAN,
    )
    return {
        "version": 1,
        "kind": "implicit_2d",
        "equation_latex": _equation_latex(left, right),
        "raw_expression": f"{left} = {right}",
        "viewport": {"x_min": view_x_min, "x_max": view_x_max, "y_min": view_y_min, "y_max": view_y_max},
        "series": [{"label": f"{left} = {right}", "segments": segments}],
    }


def build_polar_graph_spec(source: str) -> dict[str, Any]:
    node, sympy_expression = parse_graph_expression(source, {"theta"})
    samples: list[tuple[float, float] | None] = []
    values: list[float] = []
    for index in range(PARAMETRIC_SAMPLE_COUNT + 1):
        theta = 2 * math.pi * index / PARAMETRIC_SAMPLE_COUNT
        radius = _evaluate(node, {"theta": theta})
        if not math.isfinite(radius) or abs(radius) > MAX_ABS_GRAPH_VALUE:
            samples.append(None)
            continue
        x_value = radius * math.cos(theta)
        y_value = radius * math.sin(theta)
        samples.append((x_value, y_value))
        values.extend((x_value, y_value))

    x_min, x_max = _auto_range(values[::2], (-10.0, 10.0), TWO_D_MAX_VIEWPORT_SPAN)
    y_min, y_max = _auto_range(values[1::2], (-10.0, 10.0), TWO_D_MAX_VIEWPORT_SPAN)
    segments = _build_curve_segments(samples, max(x_max - x_min, y_max - y_min) * 0.45)
    if not segments:
        raise GraphingError("I could not find visible real values for that polar graph.")
    return {
        "version": 1,
        "kind": "polar_2d",
        "equation_latex": f"r = {sp.latex(sympy_expression)}",
        "raw_expression": f"r = {source}",
        "viewport": {"x_min": x_min, "x_max": x_max, "y_min": y_min, "y_max": y_max},
        "series": [{"label": f"r = {source}", "segments": segments}],
    }


def _build_parametric_components(source: str) -> tuple[dict[str, Node], dict[str, sp.Expr]]:
    components = _extract_parametric_components(source)
    if components is None:
        raise GraphingError("Use x = ..., y = ... for a parametric graph.")
    nodes: dict[str, Node] = {}
    expressions: dict[str, sp.Expr] = {}
    for axis, expression in components.items():
        node, sympy_expression = parse_graph_expression(expression, {"t"})
        nodes[axis] = node
        expressions[axis] = sympy_expression
    return nodes, expressions


def build_parametric_2d_graph_spec(source: str) -> dict[str, Any]:
    nodes, expressions = _build_parametric_components(source)
    samples: list[tuple[float, float] | None] = []
    x_values: list[float] = []
    y_values: list[float] = []
    for index in range(PARAMETRIC_SAMPLE_COUNT + 1):
        parameter = 2 * math.pi * index / PARAMETRIC_SAMPLE_COUNT
        x_value = _evaluate(nodes["x"], {"t": parameter})
        y_value = _evaluate(nodes["y"], {"t": parameter})
        if not math.isfinite(x_value) or not math.isfinite(y_value):
            samples.append(None)
            continue
        samples.append((x_value, y_value))
        x_values.append(x_value)
        y_values.append(y_value)

    x_min, x_max = _auto_range(x_values, (-10.0, 10.0), TWO_D_MAX_VIEWPORT_SPAN)
    y_min, y_max = _auto_range(y_values, (-10.0, 10.0), TWO_D_MAX_VIEWPORT_SPAN)
    segments = _build_curve_segments(samples, max(x_max - x_min, y_max - y_min) * 0.45)
    if not segments:
        raise GraphingError("I could not find visible points for that parametric curve.")
    latex = r",\quad ".join(f"{axis} = {sp.latex(expressions[axis])}" for axis in ("x", "y"))
    return {
        "version": 1,
        "kind": "parametric_2d",
        "equation_latex": latex,
        "raw_expression": source,
        "viewport": {"x_min": x_min, "x_max": x_max, "y_min": y_min, "y_max": y_max},
        "series": [{"label": source, "segments": segments}],
    }


def _parse_piecewise_condition(source: str) -> tuple[float, float]:
    source = source.strip().replace("\u2264", "<=").replace("\u2265", ">=")
    between = re.fullmatch(r"(?P<lower>.+?)\s*(?:<=|<)\s*x\s*(?:<=|<)\s*(?P<upper>.+)", source)
    if between:
        lower_node, _ = parse_graph_expression(between.group("lower"), set())
        upper_node, _ = parse_graph_expression(between.group("upper"), set())
        return _evaluate(lower_node, {}), _evaluate(upper_node, {})

    match = re.fullmatch(r"x\s*(?P<operator><=|>=|<|>)\s*(?P<value>.+)", source)
    if match is None:
        raise GraphingError("Use a piecewise condition such as x < 0 or 0 <= x <= 4.")
    value_node, _ = parse_graph_expression(match.group("value"), set())
    value = _evaluate(value_node, {})
    if not math.isfinite(value):
        raise GraphingError("Use a finite number in each piecewise condition.")
    operator = match.group("operator")
    if operator in {"<", "<="}:
        return -math.inf, value
    return value, math.inf


def build_piecewise_2d_graph_spec(source: str) -> dict[str, Any]:
    pieces: list[tuple[Node, tuple[float, float], str]] = []
    for piece in (part.strip() for part in source.split(";") if part.strip()):
        match = re.fullmatch(
            r"y\s*=\s*(?P<expression>.+?)\s+\b(?:for|when|if)\b\s+(?P<condition>.+)",
            piece,
            re.IGNORECASE,
        )
        if match is None:
            raise GraphingError("Write each piece like y = x^2 for x >= 0, separated by semicolons.")
        expression = _normalise_source(match.group("expression"))
        node, _ = parse_graph_expression(expression, {"x"})
        pieces.append((node, _parse_piecewise_condition(match.group("condition")), piece))

    if not pieces:
        raise GraphingError("Add at least one piecewise rule.")
    x_min, x_max = TWO_D_DOMAIN
    all_values: list[float] = []
    series = []
    for node, (lower, upper), label in pieces:
        samples: list[tuple[float, float] | None] = []
        for index in range(TWO_D_SAMPLE_COUNT):
            x_value = x_min + (x_max - x_min) * index / (TWO_D_SAMPLE_COUNT - 1)
            if x_value < lower or x_value > upper:
                samples.append(None)
                continue
            y_value = _evaluate(node, {"x": x_value})
            if math.isfinite(y_value) and abs(y_value) <= MAX_ABS_GRAPH_VALUE:
                samples.append((x_value, y_value))
                all_values.append(y_value)
            else:
                samples.append(None)
        segments = _build_curve_segments(samples, TWO_D_MAX_VIEWPORT_SPAN * 1.5)
        if segments:
            series.append({"label": label, "segments": segments})
    if not series:
        raise GraphingError("I could not find visible values for those piecewise rules.")
    y_min, y_max = _auto_range(all_values, (-10.0, 10.0), TWO_D_MAX_VIEWPORT_SPAN)
    return {
        "version": 1,
        "kind": "piecewise_2d",
        "equation_latex": r"\text{piecewise function}",
        "raw_expression": source,
        "viewport": {"x_min": x_min, "x_max": x_max, "y_min": y_min, "y_max": y_max},
        "series": series,
    }


def build_inequality_2d_graph_spec(source: str) -> dict[str, Any]:
    normalised = source.replace("\u2264", "<=").replace("\u2265", ">=")
    match = re.fullmatch(r"(?P<left>.+?)\s*(?P<operator><=|>=)\s*(?P<right>.+)", normalised)
    if match is None:
        raise GraphingError("Use an inequality such as y <= x^2 or x^2 + y^2 <= 25.")
    left = _normalise_source(match.group("left"))
    right = _normalise_source(match.group("right"))
    node, _ = parse_graph_expression(f"({left}) - ({right})", {"x", "y"})
    x_min, x_max = TWO_D_DOMAIN
    y_min, y_max = TWO_D_DOMAIN
    grid_size = 64
    values: list[list[float | None]] = []
    for row in range(grid_size + 1):
        y_value = y_min + (y_max - y_min) * row / grid_size
        value_row: list[float | None] = []
        for column in range(grid_size + 1):
            x_value = x_min + (x_max - x_min) * column / grid_size
            value = _evaluate(node, {"x": x_value, "y": y_value})
            value_row.append(value if math.isfinite(value) else None)
        values.append(value_row)

    accepts_negative = match.group("operator") == "<="
    positions: list[float] = []
    for row in range(grid_size):
        for column in range(grid_size):
            corners = (values[row][column], values[row][column + 1], values[row + 1][column + 1], values[row + 1][column])
            center = sum(corners) / 4 if all(value is not None for value in corners) else math.nan
            if not math.isfinite(center) or (center <= 0) != accepts_negative:
                continue
            x0 = x_min + (x_max - x_min) * column / grid_size
            x1 = x_min + (x_max - x_min) * (column + 1) / grid_size
            y0 = y_min + (y_max - y_min) * row / grid_size
            y1 = y_min + (y_max - y_min) * (row + 1) / grid_size
            positions.extend([x0, y0, x1, y0, x1, y1, x0, y0, x1, y1, x0, y1])

    boundary = _build_marching_square_segments(values, x_min, x_max, y_min, y_max)
    return {
        "version": 1,
        "kind": "inequality_2d",
        "equation_latex": _equation_latex(left, right, r"\le" if accepts_negative else r"\ge"),
        "raw_expression": f"{left} {match.group('operator')} {right}",
        "viewport": {"x_min": x_min, "x_max": x_max, "y_min": y_min, "y_max": y_max},
        "series": [{"label": source, "segments": boundary}],
        "region_positions": [_format_number(value) for value in positions],
    }


def build_vector_field_2d_graph_spec(source: str) -> dict[str, Any]:
    match = re.search(
        r"(?:vector\s+field|field)\s*(?:f\s*\(\s*x\s*,\s*y\s*\)\s*=\s*)?"
        r"<\s*(?P<x>[^,<>]+)\s*,\s*(?P<y>[^<>]+)\s*>",
        source,
        re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        raise GraphingError("Use a vector field such as vector field <y, -x>.")
    x_source = _normalise_source(match.group("x"))
    y_source = _normalise_source(match.group("y"))
    x_node, x_expression = parse_graph_expression(x_source, {"x", "y"})
    y_node, y_expression = parse_graph_expression(y_source, {"x", "y"})
    x_min, x_max = (-8.0, 8.0)
    y_min, y_max = (-8.0, 8.0)
    spacing = (x_max - x_min) / (VECTOR_FIELD_GRID_SIZE - 1)
    vectors: list[list[float]] = []
    for row in range(VECTOR_FIELD_GRID_SIZE):
        y_value = y_min + spacing * row
        for column in range(VECTOR_FIELD_GRID_SIZE):
            x_value = x_min + spacing * column
            horizontal = _evaluate(x_node, {"x": x_value, "y": y_value})
            vertical = _evaluate(y_node, {"x": x_value, "y": y_value})
            magnitude = math.hypot(horizontal, vertical)
            if not math.isfinite(magnitude) or magnitude < 1e-9:
                continue
            scale = min(spacing * 0.38 / magnitude, spacing * 0.62 / max(magnitude, 1.0))
            vectors.append([
                _format_number(x_value),
                _format_number(y_value),
                _format_number(horizontal * scale),
                _format_number(vertical * scale),
            ])
    if not vectors:
        raise GraphingError("I could not find visible arrows for that vector field.")
    return {
        "version": 1,
        "kind": "vector_field_2d",
        "equation_latex": rf"\left\langle {sp.latex(x_expression)},\, {sp.latex(y_expression)} \right\rangle",
        "raw_expression": source,
        "viewport": {"x_min": x_min, "x_max": x_max, "y_min": y_min, "y_max": y_max},
        "vectors": vectors,
    }


def build_point_graph_spec(points: tuple[tuple[float, float], ...]) -> dict[str, Any]:
    if not points:
        raise GraphingError("Add at least one point to plot.")
    x_min, x_max = _auto_range([point[0] for point in points], (-10.0, 10.0))
    y_min, y_max = _auto_range([point[1] for point in points], (-10.0, 10.0))
    formatted_points = [[_format_number(x), _format_number(y)] for x, y in points]
    label = ", ".join(f"({x:g}, {y:g})" for x, y in points)
    return {
        "version": 1,
        "kind": "points_2d",
        "equation_latex": ",\\; ".join(f"({x:g},\\, {y:g})" for x, y in points),
        "raw_expression": label,
        "viewport": {
            "x_min": x_min,
            "x_max": x_max,
            "y_min": y_min,
            "y_max": y_max,
        },
        "points": formatted_points,
    }


def build_3d_graph_spec(source: str) -> dict[str, Any]:
    node, sympy_expression = parse_graph_expression(source, {"x", "y"})
    x_min, x_max = THREE_D_DOMAIN
    y_min, y_max = THREE_D_DOMAIN
    raw_values: list[list[float | None]] = []
    finite_values: list[float] = []

    for row in range(THREE_D_GRID_SIZE):
        y_value = y_min + (y_max - y_min) * row / (THREE_D_GRID_SIZE - 1)
        raw_row: list[float | None] = []
        for column in range(THREE_D_GRID_SIZE):
            x_value = x_min + (x_max - x_min) * column / (THREE_D_GRID_SIZE - 1)
            z_value = _evaluate(node, {"x": x_value, "y": y_value})
            if math.isfinite(z_value) and abs(z_value) <= MAX_ABS_GRAPH_VALUE:
                raw_row.append(z_value)
                finite_values.append(z_value)
            else:
                raw_row.append(None)
        raw_values.append(raw_row)

    z_min, z_max = _auto_range(
        finite_values,
        (-5.0, 5.0),
        max_span=THREE_D_MAX_VIEWPORT_SPAN,
    )
    z_span = max(z_max - z_min, 1.0)
    jump_limit = max(z_span * 1.5, 10.0)

    positions: list[float] = []
    vertex_grid: list[list[int | None]] = [[None] * THREE_D_GRID_SIZE for _ in range(THREE_D_GRID_SIZE)]
    for row, values in enumerate(raw_values):
        y_value = y_min + (y_max - y_min) * row / (THREE_D_GRID_SIZE - 1)
        for column, z_value in enumerate(values):
            if z_value is None:
                continue
            x_value = x_min + (x_max - x_min) * column / (THREE_D_GRID_SIZE - 1)
            vertex_grid[row][column] = len(positions) // 3
            positions.extend([
                _format_number(x_value),
                _format_number(y_value),
                _format_number(z_value),
            ])

    indices: list[int] = []
    for row in range(THREE_D_GRID_SIZE - 1):
        for column in range(THREE_D_GRID_SIZE - 1):
            top_left = vertex_grid[row][column]
            top_right = vertex_grid[row][column + 1]
            bottom_left = vertex_grid[row + 1][column]
            bottom_right = vertex_grid[row + 1][column + 1]
            if None in {top_left, top_right, bottom_left, bottom_right}:
                continue

            nearby_values = (
                raw_values[row][column],
                raw_values[row][column + 1],
                raw_values[row + 1][column],
                raw_values[row + 1][column + 1],
            )
            if max(nearby_values) - min(nearby_values) > jump_limit:
                continue
            indices.extend([top_left, bottom_left, top_right, top_right, bottom_left, bottom_right])

    if not positions or not indices:
        raise GraphingError("I could not find a visible 3D surface for that equation.")

    return {
        "version": 1,
        "kind": "surface_3d",
        "equation_latex": sp.latex(sympy_expression),
        "raw_expression": f"z = {source}",
        "viewport": {
            "x_min": x_min,
            "x_max": x_max,
            "y_min": y_min,
            "y_max": y_max,
            "z_min": z_min,
            "z_max": z_max,
        },
        "mesh": {
            "positions": positions,
            "indices": indices,
            # Keep the original sampled grid so the renderer can draw sparse,
            # non-diagonal surface lines without evaluating student text again.
            "rows": THREE_D_GRID_SIZE,
            "columns": THREE_D_GRID_SIZE,
            "vertex_indices": vertex_grid,
        },
    }


def _interpolate_3d_zero(
    first: tuple[float, float, float],
    first_value: float,
    second: tuple[float, float, float],
    second_value: float,
) -> tuple[float, float, float]:
    denominator = first_value - second_value
    ratio = 0.5 if abs(denominator) < 1e-12 else first_value / denominator
    ratio = min(max(ratio, 0.0), 1.0)
    return tuple(
        first[index] + (second[index] - first[index]) * ratio
        for index in range(3)
    )


def _append_implicit_triangle(
    positions: list[float],
    indices: list[int],
    points: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]],
) -> None:
    start = len(positions) // 3
    for point in points:
        positions.extend(_format_number(value) for value in point)
    indices.extend((start, start + 1, start + 2))


def _build_implicit_3d_mesh(node: Node) -> dict[str, Any]:
    """Create a limited triangle mesh for F(x, y, z) = 0 using tetrahedra."""
    domain_min, domain_max = THREE_D_DOMAIN
    size = IMPLICIT_THREE_D_GRID_SIZE
    step = (domain_max - domain_min) / size
    values: list[list[list[float | None]]] = []
    for z_index in range(size + 1):
        z_value = domain_min + z_index * step
        z_plane: list[list[float | None]] = []
        for y_index in range(size + 1):
            y_value = domain_min + y_index * step
            row: list[float | None] = []
            for x_index in range(size + 1):
                x_value = domain_min + x_index * step
                value = _evaluate(node, {"x": x_value, "y": y_value, "z": z_value})
                row.append(value if math.isfinite(value) and abs(value) <= MAX_ABS_GRAPH_VALUE else None)
            z_plane.append(row)
        values.append(z_plane)

    cube_corners = (
        (0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
        (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1),
    )
    tetrahedra = (
        (0, 5, 1, 6), (0, 1, 2, 6), (0, 2, 3, 6),
        (0, 3, 7, 6), (0, 7, 4, 6), (0, 4, 5, 6),
    )
    positions: list[float] = []
    indices: list[int] = []

    for z_index in range(size):
        for y_index in range(size):
            for x_index in range(size):
                points = [
                    (
                        domain_min + (x_index + dx) * step,
                        domain_min + (y_index + dy) * step,
                        domain_min + (z_index + dz) * step,
                    )
                    for dx, dy, dz in cube_corners
                ]
                cube_values = [
                    values[z_index + dz][y_index + dy][x_index + dx]
                    for dx, dy, dz in cube_corners
                ]
                if any(value is None for value in cube_values):
                    continue

                for tetrahedron in tetrahedra:
                    tetra_points = [points[index] for index in tetrahedron]
                    tetra_values = [cube_values[index] for index in tetrahedron]
                    negative = [index for index, value in enumerate(tetra_values) if value <= 0]
                    positive = [index for index, value in enumerate(tetra_values) if value > 0]
                    if not negative or not positive:
                        continue

                    if len(negative) in {1, 3}:
                        isolated = negative[0] if len(negative) == 1 else positive[0]
                        others = positive if len(negative) == 1 else negative
                        triangle = tuple(
                            _interpolate_3d_zero(
                                tetra_points[isolated], tetra_values[isolated], tetra_points[other], tetra_values[other]
                            )
                            for other in others
                        )
                        _append_implicit_triangle(positions, indices, triangle)
                    else:
                        first_negative, second_negative = negative
                        first_positive, second_positive = positive
                        first = _interpolate_3d_zero(
                            tetra_points[first_negative], tetra_values[first_negative],
                            tetra_points[first_positive], tetra_values[first_positive],
                        )
                        second = _interpolate_3d_zero(
                            tetra_points[first_negative], tetra_values[first_negative],
                            tetra_points[second_positive], tetra_values[second_positive],
                        )
                        third = _interpolate_3d_zero(
                            tetra_points[second_negative], tetra_values[second_negative],
                            tetra_points[first_positive], tetra_values[first_positive],
                        )
                        fourth = _interpolate_3d_zero(
                            tetra_points[second_negative], tetra_values[second_negative],
                            tetra_points[second_positive], tetra_values[second_positive],
                        )
                        _append_implicit_triangle(positions, indices, (first, third, second))
                        _append_implicit_triangle(positions, indices, (second, third, fourth))

                    if len(indices) // 3 > MAX_IMPLICIT_3D_TRIANGLES:
                        raise GraphingError("That implicit 3D surface is too detailed to graph safely.")

    if not positions or not indices:
        raise GraphingError("I could not find a visible 3D surface for that equation.")
    return {"positions": positions, "indices": indices}


def _build_implicit_3d_surface_spec(source: str, color_index: int = 0) -> dict[str, Any]:
    equation = _split_equation(source)
    if equation is None:
        raise GraphingError("Use a 3D equation such as x^2 + y^2 + z^2 = 25.")
    left, right = equation
    node, _ = parse_graph_expression(f"({left}) - ({right})", {"x", "y", "z"})
    return {
        "equation_latex": _equation_latex(left, right),
        "raw_expression": f"{left} = {right}",
        "color_index": color_index,
        "mesh": _build_implicit_3d_mesh(node),
        "viewport": {
            "x_min": THREE_D_DOMAIN[0], "x_max": THREE_D_DOMAIN[1],
            "y_min": THREE_D_DOMAIN[0], "y_max": THREE_D_DOMAIN[1],
            "z_min": THREE_D_DOMAIN[0], "z_max": THREE_D_DOMAIN[1],
        },
    }


def build_implicit_3d_graph_spec(source: str) -> dict[str, Any]:
    surface = _build_implicit_3d_surface_spec(source)
    viewport = surface.pop("viewport")
    return {
        "version": 1,
        "kind": "surface_3d",
        "equation_latex": surface["equation_latex"],
        "raw_expression": surface["raw_expression"],
        "viewport": viewport,
        "mesh": surface["mesh"],
    }


def _build_explicit_intersection_curves(surfaces: tuple[SurfaceRequest, ...]) -> list[dict[str, Any]]:
    """Trace intersections for explicit z surfaces that use the same x-y domain."""
    parsed = [parse_graph_expression(surface.source, {"x", "y"})[0] for surface in surfaces]
    curves: list[dict[str, Any]] = []
    x_min, x_max = THREE_D_DOMAIN
    y_min, y_max = THREE_D_DOMAIN
    for first_index, first_surface in enumerate(surfaces):
        for second_index in range(first_index + 1, len(surfaces)):
            second_surface = surfaces[second_index]
            if first_surface.color_index == second_surface.color_index:
                continue
            values: list[list[float | None]] = []
            for row in range(THREE_D_GRID_SIZE + 1):
                y_value = y_min + (y_max - y_min) * row / THREE_D_GRID_SIZE
                value_row: list[float | None] = []
                for column in range(THREE_D_GRID_SIZE + 1):
                    x_value = x_min + (x_max - x_min) * column / THREE_D_GRID_SIZE
                    first_value = _evaluate(parsed[first_index], {"x": x_value, "y": y_value})
                    second_value = _evaluate(parsed[second_index], {"x": x_value, "y": y_value})
                    difference = first_value - second_value
                    value_row.append(difference if math.isfinite(difference) else None)
                values.append(value_row)
            segments = _build_marching_square_segments(values, x_min, x_max, y_min, y_max)
            for segment in segments:
                points = []
                for x_value, y_value in segment:
                    z_value = _evaluate(parsed[first_index], {"x": x_value, "y": y_value})
                    if math.isfinite(z_value):
                        points.append([x_value, y_value, _format_number(z_value)])
                if len(points) == 2:
                    curves.append({"points": points})
    return curves


def build_parametric_3d_graph_spec(source: str) -> dict[str, Any]:
    nodes, expressions = _build_parametric_components(source)
    samples: list[list[float]] = []
    x_values: list[float] = []
    y_values: list[float] = []
    z_values: list[float] = []
    for index in range(PARAMETRIC_SAMPLE_COUNT + 1):
        parameter = 2 * math.pi * index / PARAMETRIC_SAMPLE_COUNT
        x_value = _evaluate(nodes["x"], {"t": parameter})
        y_value = _evaluate(nodes["y"], {"t": parameter})
        z_value = _evaluate(nodes["z"], {"t": parameter})
        if not all(math.isfinite(value) and abs(value) <= MAX_ABS_GRAPH_VALUE for value in (x_value, y_value, z_value)):
            continue
        samples.append([_format_number(x_value), _format_number(y_value), _format_number(z_value)])
        x_values.append(x_value)
        y_values.append(y_value)
        z_values.append(z_value)
    if len(samples) < 2:
        raise GraphingError("I could not find visible points for that 3D parametric curve.")
    latex = r",\quad ".join(f"{axis} = {sp.latex(expressions[axis])}" for axis in ("x", "y", "z"))
    return {
        "version": 1,
        "kind": "curve_3d",
        "equation_latex": latex,
        "raw_expression": source,
        "viewport": {
            "x_min": _auto_range(x_values, THREE_D_DOMAIN, THREE_D_MAX_VIEWPORT_SPAN)[0],
            "x_max": _auto_range(x_values, THREE_D_DOMAIN, THREE_D_MAX_VIEWPORT_SPAN)[1],
            "y_min": _auto_range(y_values, THREE_D_DOMAIN, THREE_D_MAX_VIEWPORT_SPAN)[0],
            "y_max": _auto_range(y_values, THREE_D_DOMAIN, THREE_D_MAX_VIEWPORT_SPAN)[1],
            "z_min": _auto_range(z_values, THREE_D_DOMAIN, THREE_D_MAX_VIEWPORT_SPAN)[0],
            "z_max": _auto_range(z_values, THREE_D_DOMAIN, THREE_D_MAX_VIEWPORT_SPAN)[1],
        },
        "curves": [{"points": samples}],
    }


def build_3d_system_graph_spec(source: str) -> dict[str, Any]:
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    if not lines or len(lines) > MAX_3D_SURFACES:
        raise GraphingError("Graph between one and six 3D equations at one time.")

    explicit_surfaces: list[SurfaceRequest] = []
    surface_specs: list[dict[str, Any]] = []
    for color_index, line in enumerate(lines):
        squared_match = re.fullmatch(r"z\s*(?:\^\s*2|\u00b2)\s*=\s*(?P<rhs>.+)", line, re.IGNORECASE)
        explicit_match = re.fullmatch(r"z\s*=\s*(?P<rhs>.+)", line, re.IGNORECASE)
        if squared_match:
            rhs = _normalise_source(squared_match.group("rhs"))
            explicit_surfaces.extend((
                SurfaceRequest(f"sqrt ({rhs})", f"z = sqrt({rhs})", color_index),
                SurfaceRequest(f"-sqrt ({rhs})", f"z = -sqrt({rhs})", color_index),
            ))
            continue
        if explicit_match:
            rhs = _normalise_source(explicit_match.group("rhs"))
            explicit_surfaces.append(SurfaceRequest(rhs, f"z = {rhs}", color_index))
            continue
        surface_specs.append(_build_implicit_3d_surface_spec(line, color_index))

    if len(explicit_surfaces) + len(surface_specs) > MAX_3D_SURFACES:
        raise GraphingError("Graph up to six 3D surfaces at one time.")
    for surface in explicit_surfaces:
        graph = build_3d_graph_spec(surface.source)
        surface_specs.append({
            "equation_latex": f"z = {graph['equation_latex']}",
            "raw_expression": surface.label,
            "color_index": surface.color_index,
            "mesh": graph["mesh"],
            "viewport": graph["viewport"],
        })
    if not surface_specs:
        raise GraphingError("Add a supported 3D equation to graph.")

    viewport = {
        axis + bound: (min if bound == "_min" else max)(surface["viewport"][axis + bound] for surface in surface_specs)
        for axis in ("x", "y", "z")
        for bound in ("_min", "_max")
    }
    for surface in surface_specs:
        surface.pop("viewport")

    return {
        "version": 1,
        "kind": "surface_3d",
        "equation_latex": r",\quad ".join(surface["equation_latex"] for surface in surface_specs),
        "raw_expression": "\n".join(lines),
        "surface_count": len(surface_specs),
        "viewport": viewport,
        "surfaces": surface_specs,
        "curves": _build_explicit_intersection_curves(tuple(explicit_surfaces)),
    }


def build_3d_surface_system_spec(surfaces: tuple[SurfaceRequest, ...]) -> dict[str, Any]:
    """Build several explicit 3D surfaces in a shared coordinate frame."""
    if not surfaces:
        raise GraphingError("Add at least one 3D surface to graph.")

    surface_specs: list[dict[str, Any]] = []
    for surface in surfaces:
        graph = build_3d_graph_spec(surface.source)
        surface_specs.append({
            "equation_latex": f"z = {graph['equation_latex']}",
            "raw_expression": surface.label,
            "color_index": surface.color_index,
            "mesh": graph["mesh"],
            "viewport": graph["viewport"],
        })

    x_min = min(surface["viewport"]["x_min"] for surface in surface_specs)
    x_max = max(surface["viewport"]["x_max"] for surface in surface_specs)
    y_min = min(surface["viewport"]["y_min"] for surface in surface_specs)
    y_max = max(surface["viewport"]["y_max"] for surface in surface_specs)
    z_min = min(surface["viewport"]["z_min"] for surface in surface_specs)
    z_max = max(surface["viewport"]["z_max"] for surface in surface_specs)

    for surface in surface_specs:
        surface.pop("viewport")

    equation_latex = r",\quad ".join(surface["equation_latex"] for surface in surface_specs)
    raw_expression = "\n".join(surface.label for surface in surfaces)
    return {
        "version": 1,
        "kind": "surface_3d",
        "equation_latex": equation_latex,
        "raw_expression": raw_expression,
        "surface_count": len(surface_specs),
        "viewport": {
            "x_min": x_min,
            "x_max": x_max,
            "y_min": y_min,
            "y_max": y_max,
            "z_min": z_min,
            "z_max": z_max,
        },
        "surfaces": surface_specs,
    }


def build_graph_spec(message: str) -> dict[str, Any] | None:
    """Build safe JSON-ready data for one supported graph request."""
    request = extract_graph_request(message)
    if request is None:
        return None
    if request.kind == "points_2d":
        return build_point_graph_spec(request.points)
    if request.kind == "implicit_2d":
        return build_implicit_2d_graph_spec(request.source)
    if request.kind == "polar_2d":
        return build_polar_graph_spec(request.source)
    if request.kind == "parametric_2d":
        return build_parametric_2d_graph_spec(request.source)
    if request.kind == "piecewise_2d":
        return build_piecewise_2d_graph_spec(request.source)
    if request.kind == "inequality_2d":
        return build_inequality_2d_graph_spec(request.source)
    if request.kind == "vector_field_2d":
        return build_vector_field_2d_graph_spec(request.source)
    if request.kind == "curve_3d":
        return build_parametric_3d_graph_spec(request.source)
    if request.kind == "implicit_3d":
        return build_implicit_3d_graph_spec(request.source)
    if request.kind == "system_3d":
        return build_3d_system_graph_spec(request.source)
    if request.kind == "surface_3d":
        if request.surfaces:
            return build_3d_surface_system_spec(request.surfaces)
        return build_3d_graph_spec(request.source)
    return build_2d_graph_spec(request.source)
