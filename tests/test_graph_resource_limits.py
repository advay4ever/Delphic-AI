import subprocess
import sys

import pytest

from ai import graphing


@pytest.mark.parametrize("operation", ["+", "-", "*", "/"])
def test_graph_converter_only_evaluates_the_requested_operation(monkeypatch, operation):
    calls = []

    class Tracer:
        is_Rational = False
        def __add__(self, other):
            calls.append("+")
            return self
        def __sub__(self, other):
            calls.append("-")
            return self
        def __mul__(self, other):
            calls.append("*")
            return self
        def __truediv__(self, other):
            calls.append("/")
            return self
        def __pow__(self, other):
            raise AssertionError("An unrelated power must not run")

    monkeypatch.setattr(graphing.sp, "Symbol", lambda *args, **kwargs: Tracer())
    graphing._to_sympy(graphing.Node("binary", operation, graphing.Node("variable", "x"), graphing.Node("variable", "y")))
    assert calls == [operation]


@pytest.mark.parametrize("expression,expected", [
    ("y = 1000000 - 999999", "1"),
    ("y = 2 + 3", "5"),
])
def test_original_constant_graph_probe_finishes_in_a_child_process(expression, expected):
    result = subprocess.run(
        [sys.executable, "-c", "from ai.graphing import build_graph_spec; "
         f"print(build_graph_spec({expression!r})['equation_latex'])"],
        capture_output=True, text=True, timeout=5, check=True,
    )
    assert result.stdout.strip() == expected


@pytest.mark.parametrize("expression", [
    "y=((((10^32)^32)^32)^32)",
    "y=((((x^32)^32)^32)^32)",
    "z=((((10^32)^32)^32)^32)+y",
    "y=1/((((10^32)^32)^32)^32)",
])
def test_nested_power_rejection_has_a_process_safety_deadline(expression):
    result = subprocess.run(
        [sys.executable, "-c", "from ai.graphing import build_graph_spec, GraphingError\n"
         f"try: build_graph_spec({expression!r})\n"
         "except GraphingError: print('rejected')\n"
         "else: raise AssertionError('Expected a bounded rejection')"],
        capture_output=True, text=True, timeout=5, check=True,
    )
    assert result.stdout.strip() == "rejected"


def test_square_roots_and_functions_keep_bounded_symbolic_labels():
    assert graphing.build_graph_spec("y=sqrt(x^2+1)")["series"][0]["segments"]
    assert graphing.build_graph_spec("z=sin(x)*cos(y)")["mesh"]["indices"]
