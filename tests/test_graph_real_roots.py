import math

import pytest

from ai.graphing import _evaluate, build_graph_spec, parse_graph_expression


@pytest.mark.parametrize("expression,expected", [
    ("x^(1/3)", -2), ("x^(2/3)", 4), ("x^(-1/3)", -0.5),
    ("x^(2/6)", -2), ("x^(1/(2+1))", -2), ("x^(-2/3)", 0.25),
])
def test_odd_denominator_powers_have_real_negative_branches(expression, expected):
    node, _ = parse_graph_expression(expression, {"x"})
    assert _evaluate(node, {"x": -8.0}) == pytest.approx(expected)


@pytest.mark.parametrize("expression", ["x^(1/3)", "x^(2/3)"])
def test_real_root_graph_includes_both_sides_of_zero(expression):
    graph = build_graph_spec(f"Graph y={expression}")
    points = [point for series in graph["series"] for segment in series["segments"] for point in segment]
    assert any(x < 0 for x, y in points)
    assert any(x > 0 for x, y in points)
    assert any(x == 0 and y == 0 for x, y in points)


@pytest.mark.parametrize("expression", ["sqrt(x)", "x^(1/2)", "x^(1/6)", "x^pi", "x^0.3333333333333333"])
def test_nonreal_powers_are_not_guessed_to_be_real(expression):
    node, _ = parse_graph_expression(expression, {"x"})
    assert math.isnan(_evaluate(node, {"x": -8.0}))


def test_reciprocal_cube_root_remains_undefined_at_zero():
    node, _ = parse_graph_expression("x^(-1/3)", {"x"})
    assert math.isnan(_evaluate(node, {"x": 0.0}))


def test_3d_surface_uses_the_same_real_root_semantics():
    graph = build_graph_spec("Graph z=x^(1/3)+y")
    positions = graph["mesh"]["positions"]
    assert any(positions[index] < 0 for index in range(0, len(positions), 3))
