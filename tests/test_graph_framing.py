import pytest

from ai.graphing import build_graph_spec


@pytest.mark.parametrize("equation", ["y=100", "y=-100", "y=x+1000", "y=x-1000"])
def test_shifted_2d_graphs_contain_visible_curve_points(equation):
    spec = build_graph_spec("Graph " + equation)
    viewport = spec["viewport"]
    points = [p for series in spec["series"] for segment in series["segments"] for p in segment]
    assert any(viewport["y_min"] <= y <= viewport["y_max"] for x, y in points)
    assert viewport["y_max"] - viewport["y_min"] <= 24.000001


@pytest.mark.parametrize("equation", ["z=100", "z=-100", "z=x^2+y^2+100", "z=x^2+y^2-100"])
def test_shifted_surfaces_have_vertices_inside_the_viewing_range(equation):
    spec = build_graph_spec("Graph " + equation)
    viewport = spec["viewport"]
    heights = spec["mesh"]["positions"][2::3]
    assert any(viewport["z_min"] < z < viewport["z_max"] for z in heights)
    assert viewport["z_max"] - viewport["z_min"] <= 18.000001


def test_separated_surfaces_share_a_range_that_contains_both():
    spec = build_graph_spec("Graph z=100\nz=-100")
    assert spec["surface_count"] == 2
    for surface in spec["surfaces"]:
        assert any(spec["viewport"]["z_min"] < z < spec["viewport"]["z_max"]
                   for z in surface["mesh"]["positions"][2::3])
