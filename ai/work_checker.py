"""Strict local verification for a student's written math steps."""

from __future__ import annotations

import re
import multiprocessing
import sys
from dataclasses import dataclass

import sympy as sp
from sympy.calculus.util import continuous_domain
from ai.safe_math import MathInputError, parse_math


MAX_STEP_LENGTH = 160
MAX_PARSED_STEPS = 12
MAX_EXPRESSION_OPERATIONS = 60
MAX_WORK_CHECK_SECONDS = 4
MAX_WORK_TEXT = 2000
MAX_REFERENCE_TEXT = 48_000
APPROVED_NAMES = {
    "abs": sp.Abs,
    "cos": sp.cos,
    "e": sp.E,
    "exp": sp.exp,
    "ln": sp.log,
    "log": sp.log,
    "pi": sp.pi,
    "sin": sp.sin,
    "sqrt": sp.sqrt,
    "tan": sp.tan,
}
CHECK_PHRASES = (
    "check my work",
    "check my answer",
    "check this work",
    "is this right",
    "is that right",
    "is this correct",
    "is my answer correct",
    "am i right",
    "where did i mess up",
    "find my mistake",
    "here is my work",
    "heres my work",
)
LEADING_WORDS = re.compile(
    r"^(?:(?:step\s*\d+)\s*[:.)-]\s*|"
    r"(?:\d+)\s*(?:[:)-]|\.(?!\d))\s*|"
    r"(?:then|therefore|next|finally|solve|try|my answer|i got|so|answer)\b\s*[:,-]?\s*)",
    re.IGNORECASE,
)
TRAILING_QUESTION = re.compile(
    r"\s*[,;]?\s*(?:is (?:this|that|it) (?:right|correct)|am i right)\??\s*$",
    re.IGNORECASE,
)
SAFE_EXPRESSION = re.compile(r"^[0-9A-Za-z+\-*/^().\s]+$")
SUPERSCRIPT_REPLACEMENTS = str.maketrans({
    "⁰": "^0",
    "¹": "^1",
    "²": "^2",
    "³": "^3",
    "⁴": "^4",
    "⁵": "^5",
    "⁶": "^6",
    "⁷": "^7",
    "⁸": "^8",
    "⁹": "^9",
})


@dataclass(frozen=True)
class EquationStep:
    text: str
    left: sp.Expr
    right: sp.Expr
    submitted_number: int
    is_reference: bool = False

    @property
    def symbols(self) -> set[sp.Symbol]:
        return self.left.free_symbols | self.right.free_symbols

    @property
    def latex(self) -> str:
        return f"{sp.latex(self.left)} = {sp.latex(self.right)}"


@dataclass(frozen=True)
class FunctionStep:
    text: str
    expression: sp.Expr
    variable: sp.Symbol
    derivative_order: int
    submitted_number: int
    is_reference: bool = False

    @property
    def latex(self) -> str:
        if self.derivative_order == 0:
            left = f"f({sp.latex(self.variable)})"
        else:
            left = f"f^{{({self.derivative_order})}}({sp.latex(self.variable)})"
        return f"{left} = {sp.latex(self.expression)}"


MathStep = EquationStep | FunctionStep


@dataclass(frozen=True)
class WorkCheckResult:
    status: str
    checked_transitions: int
    current_step_number: int | None = None
    previous_step: str | None = None
    current_step: str | None = None
    reason: str = ""

    def to_prompt_context(self) -> str:
        """Create a factual system note without asking the model to recompute it."""
        if self.status == "correct":
            return (
                "VERIFIED LOCAL WORK CHECK: SymPy checked "
                f"{self.checked_transitions} transition(s), and every checked step preserves "
                "the same answer. Tell the student the checked work is correct. Keep the reply "
                "brief and explain one key reason. Do not invent a mistake."
            )

        step_label = (
            f"student step {self.current_step_number}"
            if self.current_step_number is not None
            else "the student's step"
        )
        return (
            "VERIFIED LOCAL WORK CHECK: SymPy found the first incorrect transition at "
            f"{step_label}. Previous step: $${self.previous_step}$$ Current step: "
            f"$${self.current_step}$$ Verified reason: {self.reason} "
            "Treat this as the mathematical source of truth. Point to this first issue, explain "
            "it simply, and give only the next correction step unless the student asks for the "
            "complete solution. Do not claim that a later step was the first mistake."
        )


def looks_like_work_check_request(text: str) -> bool:
    lowered = text.casefold()
    if any(phrase in lowered for phrase in CHECK_PHRASES):
        return True
    lines = re.split(r"[\n;]+|->|=>|\u2192|\u21d2", text)
    return sum(_clean_candidate_line(line) is not None for line in lines) >= 2


def check_math_work(
    student_text: str,
    conversation: list[dict] | None = None,
    *,
    compare_to_reference: bool = False,
) -> WorkCheckResult | None:
    """Verify in a disposable process; timeout/failure never means verified."""
    if not isinstance(student_text, str) or len(student_text) > MAX_WORK_TEXT:
        return None
    # Reference verification never needs attachment bytes or other chat metadata.
    prior = [{"content": message["content"]} for message in (conversation or [])[-12:]
             if isinstance(message, dict) and isinstance(message.get("content"), str)]
    if sum(len(message["content"]) for message in prior) > MAX_REFERENCE_TEXT:
        return None
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=_work_check_worker,
                              args=(child, student_text, prior, compare_to_reference), daemon=True)
    try:
        process.start()
        child.close()
        if parent.poll(MAX_WORK_CHECK_SECONDS):
            result = parent.recv()
            return result if isinstance(result, WorkCheckResult) else None
    except (EOFError, OSError, RuntimeError, ValueError):
        return None
    finally:
        if process.pid is not None:
            if process.is_alive():
                process.terminate()
            process.join(timeout=1)
            if process.is_alive():
                process.kill()
                process.join(timeout=1)
        parent.close()
        child.close()
    return None


def _work_check_worker(connection, student_text, conversation, compare_to_reference):
    try:
        if sys.platform.startswith("linux"):
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
        result = _check_math_work(student_text, conversation, compare_to_reference=compare_to_reference)
        connection.send(result)
    except Exception:
        connection.send(None)
    finally:
        connection.close()


def _check_math_work(student_text, conversation=None, *, compare_to_reference=False):
    submitted_steps, rejected_step = _extract_math_step_report(student_text)
    if not submitted_steps or rejected_step:
        return None

    steps: list[MathStep] = list(submitted_steps)
    if len(steps) == 1 or compare_to_reference:
        reference = find_latest_reference_step(conversation or [])
        if reference is None and len(steps) == 1:
            return None
        if reference is not None:
            steps.insert(0, reference)

    checked = 0
    for previous, current in zip(steps, steps[1:]):
        comparison = _compare_steps(previous, current)
        if comparison is None:
            return None
        is_valid, reason = comparison
        checked += 1
        if not is_valid:
            return WorkCheckResult(
                status="incorrect",
                checked_transitions=checked,
                current_step_number=current.submitted_number or None,
                previous_step=previous.latex,
                current_step=current.latex,
                reason=reason,
            )

    if checked == 0:
        return None
    return WorkCheckResult(status="correct", checked_transitions=checked)


def extract_math_steps(text: str, *, is_reference: bool = False) -> list[MathStep]:
    """Extract a small, ordered set of supported equations from ordinary text."""
    steps, _rejected_step = _extract_math_step_report(text, is_reference=is_reference)
    return steps


def _extract_math_step_report(
    text: str,
    *,
    is_reference: bool = False,
) -> tuple[list[MathStep], bool]:
    steps: list[MathStep] = []
    rejected_step = False
    candidate_number = 0
    normalized_text = _normalize_latex_text(text.replace("```", ""))
    normalized_text = re.sub(r"\s*(?:->|=>|→|⇒)\s*", "\n", normalized_text)
    pieces = re.split(r"[\n;]+", normalized_text)
    for raw_line in pieces:
        clean = _clean_candidate_line(raw_line)
        if clean is None:
            if "=" in raw_line:
                rejected_step = True
            continue
        candidate_number += 1
        if candidate_number > MAX_PARSED_STEPS:
            return steps, True
        submitted_number = 0 if is_reference else candidate_number
        parsed = _parse_step(clean, submitted_number, is_reference)
        if parsed is not None:
            steps.append(parsed)
        else:
            rejected_step = True
    return steps, rejected_step


def find_latest_reference_step(conversation: list[dict]) -> MathStep | None:
    """Find the first equation in the closest earlier chat message containing math."""
    for message in reversed(conversation[-12:]):
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            continue
        steps, rejected_step = _extract_math_step_report(content, is_reference=True)
        if steps and not rejected_step:
            return steps[0]
    return None


def _clean_candidate_line(raw_line: str) -> str | None:
    line = raw_line.strip().strip("$` ")
    line = re.sub(r"^[-*•]+\s*", "", line)
    if ":" in line and "=" in line.split(":", 1)[1]:
        line = line.split(":", 1)[1].strip()
    for _ in range(2):
        line = LEADING_WORDS.sub("", line).strip()
    line = TRAILING_QUESTION.sub("", line).strip().rstrip(".,")
    line = (
        line.replace("−", "-")
        .replace("×", "*")
        .replace("÷", "/")
        .replace("′", "'")
    )
    if not line or len(line) > MAX_STEP_LENGTH or line.count("=") != 1:
        return None
    if any(token in line for token in ("==", "<=", ">=", "!=", "=>", "=<")):
        return None
    return line


def _normalize_latex_text(text: str) -> str:
    normalized = re.sub(r"\\(?:begin|end)\{(?:aligned|align\*?|equation\*?)\}", "", text)
    normalized = normalized.replace("\\\\", "\n")
    normalized = (
        normalized.replace("\\(", "")
        .replace("\\)", "")
        .replace("\\[", "")
        .replace("\\]", "")
        .replace("\\left", "")
        .replace("\\right", "")
        .replace("\\cdot", "*")
        .replace("\\times", "*")
        .replace("\\div", "/")
        .replace("&", "")
        .translate(SUPERSCRIPT_REPLACEMENTS)
    )
    simple_group = r"([^{}]+)"
    for _ in range(3):
        updated = re.sub(
            rf"\\frac\{{{simple_group}\}}\{{{simple_group}\}}",
            r"(\1)/(\2)",
            normalized,
        )
        updated = re.sub(rf"\\sqrt\{{{simple_group}\}}", r"sqrt(\1)", updated)
        if updated == normalized:
            break
        normalized = updated
    normalized = re.sub(r"\^\{([^{}]+)\}", r"^(\1)", normalized)
    return normalized


def _parse_step(text: str, submitted_number: int, is_reference: bool) -> MathStep | None:
    function_step = _parse_function_step(text, submitted_number, is_reference)
    if function_step is not None:
        return function_step

    left_text, right_text = (part.strip() for part in text.split("=", 1))
    left = _parse_safe_expression(left_text)
    right = _parse_safe_expression(right_text)
    if left is None or right is None:
        return None
    symbols = left.free_symbols | right.free_symbols
    if len(symbols) > 1:
        return None
    return EquationStep(text, left, right, submitted_number, is_reference)


def _parse_function_step(
    text: str,
    submitted_number: int,
    is_reference: bool,
) -> FunctionStep | None:
    left_text, right_text = (part.strip() for part in text.split("=", 1))
    compact_left = re.sub(r"\s+", "", left_text)
    match = re.fullmatch(r"f(?P<primes>'{0,3})\((?P<variable>[A-Za-z])\)", compact_left)
    if match is None:
        match = re.fullmatch(r"y(?P<primes>'{0,3})", compact_left)
        variable_name = "x"
    else:
        variable_name = match.group("variable").lower()
    if match is None:
        return None
    expression = _parse_safe_expression(right_text)
    if expression is None:
        return None
    variable = sp.Symbol(variable_name)
    if expression.free_symbols - {variable}:
        return None
    return FunctionStep(
        text=text,
        expression=expression,
        variable=variable,
        derivative_order=len(match.group("primes")),
        submitted_number=submitted_number,
        is_reference=is_reference,
    )


def _parse_safe_expression(source: str) -> sp.Expr | None:
    if not source or len(source) > MAX_STEP_LENGTH or not SAFE_EXPRESSION.fullmatch(source):
        return None
    if source.count("(") != source.count(")") or source.count("(") > 12:
        return None
    if ".." in source or re.search(r"\d{13,}", source):
        return None
    exponent_matches = re.findall(r"(?:\^|\*\*)\s*\(?\s*(\d+)", source)
    if any(int(exponent) > 20 for exponent in exponent_matches):
        return None

    names = set(re.findall(r"[A-Za-z]+", source))
    if any(len(name) > 1 and name.casefold() not in APPROVED_NAMES for name in names):
        return None

    try:
        expression = parse_math(source.lower(), exact=True, evaluate=False)
    except (MathInputError, ArithmeticError, TypeError, ValueError):
        return None
    if not isinstance(expression, sp.Expr) or sp.count_ops(expression) > MAX_EXPRESSION_OPERATIONS:
        return None
    if expression.has(sp.nan, sp.zoo, sp.oo, -sp.oo):
        return None
    return expression


def _compare_steps(previous: MathStep, current: MathStep) -> tuple[bool, str] | None:
    if isinstance(previous, FunctionStep) or isinstance(current, FunctionStep):
        if not isinstance(previous, FunctionStep) or not isinstance(current, FunctionStep):
            return None
        if previous.variable != current.variable:
            return None
        if current.derivative_order != previous.derivative_order + 1:
            return None
        # Restricted-domain derivative claims need more context than a formula.
        if any(continuous_domain(step.expression, step.variable, sp.S.Reals) != sp.S.Reals
               for step in (previous, current)):
            return None
        expected = sp.diff(previous.expression, previous.variable)
        difference = sp.simplify(expected - current.expression)
        if difference == 0:
            return True, "The derivative matches the previous function."
        return (
            False,
            "Differentiating the previous expression gives "
            f"$${sp.latex(expected)}$$, not $${sp.latex(current.expression)}$$.",
        )

    symbols = previous.symbols | current.symbols
    if len(symbols) > 1:
        return None
    if not symbols:
        previous_truth = sp.simplify(previous.left - previous.right) == 0
        current_truth = sp.simplify(current.left - current.right) == 0
        if previous_truth and current_truth:
            return True, "Both number statements are true."
        return False, "At least one of these number statements is not true."

    variable = next(iter(symbols))
    previous_solutions = _real_solution_set(previous, variable)
    current_solutions = _real_solution_set(current, variable)
    if previous_solutions is None or current_solutions is None:
        return None
    if previous_solutions == current_solutions:
        return True, "Both equations have the same real solution set."
    return (
        False,
        f"The previous equation has solution set $${sp.latex(previous_solutions)}$$, "
        f"but the new equation has $${sp.latex(current_solutions)}$$.",
    )


def _real_solution_set(step: EquationStep, variable: sp.Symbol) -> sp.Set | None:
    try:
        domain = continuous_domain(step.left, variable, sp.S.Reals).intersect(
            continuous_domain(step.right, variable, sp.S.Reals))
        result = sp.solveset(
            sp.Eq(step.left, step.right, evaluate=False),
            variable,
            domain=domain,
        )
    except Exception:
        return None
    if result.has(sp.ConditionSet):
        return None
    return result.intersect(domain)
