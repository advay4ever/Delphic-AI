import math

import pytest

import app as app_module
from ai.graphing import GraphingError, THREE_D_GRID_SIZE, build_graph_spec


def test_builds_a_2d_parabola_with_an_automatic_viewport():
    graph = build_graph_spec("Graph y = x^2 - 4")

    assert graph["kind"] == "function_2d"
    assert graph["equation_latex"] == "x^{2} - 4"
    assert graph["viewport"]["y_min"] < -4
    assert graph["viewport"]["y_max"] > 10
    assert graph["viewport"]["y_max"] - graph["viewport"]["y_min"] <= 24
    assert graph["series"][0]["segments"]


@pytest.mark.parametrize(
    "message",
    [
        ", , , Graph y = x^2 - 4, , ,",
        '"Graph y = x^2 - 4."',
    ],
)
def test_accepts_harmless_punctuation_around_a_graph_request(message):
    graph = build_graph_spec(message)

    assert graph["kind"] == "function_2d"
    assert graph["equation_latex"] == "x^{2} - 4"


def test_preserves_current_short_trig_and_implicit_multiplication_notation():
    graph = build_graph_spec("plot sin x")
    cosine_graph = build_graph_spec("y = 2cos(x - pi/2)")

    assert graph["kind"] == "function_2d"
    assert cosine_graph["kind"] == "function_2d"


def test_accepts_function_notation_and_unicode_superscripts():
    graph = build_graph_spec("f(x) = x\u00b2 + 1")

    assert graph["kind"] == "function_2d"
    assert graph["equation_latex"] == "x^{2} + 1"


def test_accepts_python_style_powers_from_the_follow_up_graph_resolver():
    graph = build_graph_spec("plot 2*x**2 + 1")

    assert graph["kind"] == "function_2d"


def test_splits_a_discontinuous_2d_graph_into_segments():
    graph = build_graph_spec("Graph y = 1/x")

    assert len(graph["series"][0]["segments"]) == 2


def test_builds_a_point_graph():
    graph = build_graph_spec("Plot (1, 2), (3, 4), (-2, 1)")

    assert graph["kind"] == "points_2d"
    assert graph["points"] == [[1.0, 2.0], [3.0, 4.0], [-2.0, 1.0]]
    assert graph["viewport"]["x_min"] < -2
    assert graph["viewport"]["y_max"] > 4


def test_builds_an_implicit_2d_conic_section():
    graph = build_graph_spec("Graph x^2 / 9 + y^2 / 4 = 1")

    assert graph["kind"] == "implicit_2d"
    assert graph["series"][0]["segments"]
    assert "=" in graph["equation_latex"]
    assert graph["viewport"]["x_max"] - graph["viewport"]["x_min"] < 10
    assert graph["viewport"]["y_max"] - graph["viewport"]["y_min"] < 8


def test_builds_polar_and_parametric_2d_curves():
    polar = build_graph_spec("Graph r = 2sin(3theta)")
    parametric = build_graph_spec("Graph x = cos(t), y = sin(t)")

    assert polar["kind"] == "polar_2d"
    assert polar["series"][0]["segments"]
    assert parametric["kind"] == "parametric_2d"
    assert parametric["series"][0]["segments"]


def test_builds_piecewise_functions_and_shaded_inequalities():
    piecewise = build_graph_spec("Graph y = x^2 for x >= 0; y = -x for x < 0")
    inequality = build_graph_spec("Graph x^2 + y^2 <= 25")

    assert piecewise["kind"] == "piecewise_2d"
    assert len(piecewise["series"]) == 2
    assert inequality["kind"] == "inequality_2d"
    assert inequality["region_positions"]
    assert inequality["series"][0]["segments"]


def test_builds_a_two_dimensional_vector_field():
    graph = build_graph_spec("Graph vector field <y, -x>")

    assert graph["kind"] == "vector_field_2d"
    assert len(graph["vectors"]) > 50


def test_builds_a_3d_surface_with_bounded_mesh_data():
    graph = build_graph_spec("Graph z = x^2 + y^2")

    assert graph["kind"] == "surface_3d"
    assert 10 < graph["viewport"]["z_max"] <= 18
    assert len(graph["mesh"]["positions"]) <= THREE_D_GRID_SIZE * THREE_D_GRID_SIZE * 3
    assert graph["mesh"]["indices"]
    assert all(math.isfinite(value) for value in graph["mesh"]["positions"])
    assert graph["mesh"]["rows"] == THREE_D_GRID_SIZE
    assert graph["mesh"]["columns"] == THREE_D_GRID_SIZE
    assert len(graph["mesh"]["vertex_indices"]) == THREE_D_GRID_SIZE
    assert all(len(row) == THREE_D_GRID_SIZE for row in graph["mesh"]["vertex_indices"])

    vertex_count = len(graph["mesh"]["positions"]) // 3
    vertex_indices = [index for row in graph["mesh"]["vertex_indices"] for index in row]
    assert all(index is None or 0 <= index < vertex_count for index in vertex_indices)
    assert {index for index in vertex_indices if index is not None} == set(range(vertex_count))


def test_builds_a_trigonometric_3d_surface():
    graph = build_graph_spec("Graph z = sin(x) * cos(y)")

    assert graph["kind"] == "surface_3d"
    assert graph["mesh"]["indices"]


def test_builds_an_implicit_3d_sphere():
    graph = build_graph_spec("Graph x^2 + y^2 + z^2 = 16")

    assert graph["kind"] == "surface_3d"
    assert graph["mesh"]["indices"]
    assert len(graph["mesh"]["indices"]) // 3 < 30_000


def test_builds_a_parametric_three_dimensional_curve():
    graph = build_graph_spec("Graph x = cos(t), y = sin(t), z = t / 2")

    assert graph["kind"] == "curve_3d"
    assert len(graph["curves"][0]["points"]) > 100


def test_builds_a_cone_and_plane_as_a_shared_3d_system():
    graph = build_graph_spec("z^2 = x^2 + y^2\nz = x + 2")

    assert graph["kind"] == "surface_3d"
    assert graph["surface_count"] == 3
    assert len(graph["surfaces"]) == 3
    assert graph["viewport"]["z_min"] < 0 < graph["viewport"]["z_max"]
    assert graph["surfaces"][0]["color_index"] == graph["surfaces"][1]["color_index"]
    assert graph["surfaces"][2]["color_index"] != graph["surfaces"][0]["color_index"]
    assert all(surface["mesh"]["indices"] for surface in graph["surfaces"])
    assert graph["curves"]


def test_builds_a_mixed_implicit_and_explicit_3d_system():
    graph = build_graph_spec("x^2 + y^2 + z^2 = 16\nz = x")

    assert graph["kind"] == "surface_3d"
    assert graph["surface_count"] == 2
    assert all(surface["mesh"]["indices"] for surface in graph["surfaces"])


@pytest.mark.parametrize(
    "message",
    [
        "Graph z = sin(\u221a(x\u00b2 + y\u00b2))",
        "Graph z = sqrtx^2 + y^2",
    ],
)
def test_builds_3d_surfaces_with_square_root_shorthand(message):
    graph = build_graph_spec(message)

    assert graph["kind"] == "surface_3d"
    assert graph["mesh"]["indices"]


@pytest.mark.parametrize(
    "message",
    [
        "Graph __import__('os')",
        "Graph y = x^100",
        "Graph y = [x]",
        "Graph y = unknown(x)",
    ],
)
def test_rejects_code_like_or_unbounded_graph_input(message):
    with pytest.raises(GraphingError):
        build_graph_spec(message)


def test_non_graph_text_is_not_treated_as_a_graph_request():
    assert build_graph_spec("Explain the chain rule") is None


def test_plot_endpoint_handles_an_explicit_local_graph_without_an_ai_provider(monkeypatch):
    monkeypatch.setattr(app_module, "get_session_id", lambda *_args: "test-graph-session")
    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: None)
    monkeypatch.setattr(app_module, "save_last_equation", lambda *_args, **_kwargs: None)

    client = app_module.app.test_client()
    response = client.post("/plot", json={"message": "Graph y = x^2 - 4"})

    assert response.status_code == 200
    assert response.get_json()["kind"] == "function_2d"


def test_plot_endpoint_returns_a_student_friendly_parse_error(monkeypatch):
    monkeypatch.setattr(app_module, "get_session_id", lambda *_args: "test-graph-session")
    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: None)

    client = app_module.app.test_client()
    response = client.post("/plot", json={"message": "Graph y = x^100"})

    assert response.status_code == 400
    assert "smaller numeric exponent" in response.get_json()["error"]


def test_local_graph_message_saves_a_chat_without_an_ai_provider(monkeypatch):
    saved_messages = []
    monkeypatch.setattr(app_module, "get_session_id", lambda *_args: "test-graph-session")
    monkeypatch.setattr(
        app_module,
        "save_message",
        lambda session_id, role, content: saved_messages.append((session_id, role, content)),
    )
    monkeypatch.setattr(app_module, "get_total_tokens", lambda _session_id: 0)

    client = app_module.app.test_client()
    response = client.post("/local-graph-message", json={"message": "Graph z = x^2 + y^2"})

    assert response.status_code == 200
    assert saved_messages[0] == ("test-graph-session", "user", "Graph z = x^2 + y^2")
    assert saved_messages[1][1] == "assistant"


def test_math_page_uses_local_three_assets_instead_of_desmos():
    client = app_module.app.test_client()
    response = client.get("/")

    assert response.status_code == 200
    assert b"desmos.com" not in response.data
    assert b"vendor/three/three.module.js" in response.data
    assert client.get("/static/vendor/three/three.module.js").status_code == 200
    assert client.get("/static/vendor/three/three.core.js").status_code == 200
    assert client.get("/static/vendor/three/addons/controls/OrbitControls.js").status_code == 200
