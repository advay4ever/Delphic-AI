import json
import sqlite3

import pytest

import app as app_module
import database
from ai.service import AIResponse, AIStreamEvent, FINISH_REASON_COMPLETE
from science.diagram_spec import DiagramValidationError, validate_diagram_spec
from science.diagram_templates import build_science_diagram


SUPPORTED_REQUESTS = (
    ("Draw a free-body force diagram for a box", "force_diagram"),
    ("Show me a diagram of a battery and resistor circuit", "circuit_diagram"),
    ("Can you draw a water cycle diagram?", "process_diagram"),
    ("Show me a picture of a plant cell", "labeled_structure"),
)


@pytest.mark.parametrize(("request_text", "diagram_type"), SUPPORTED_REQUESTS)
def test_reviewed_science_diagrams_are_valid(request_text, diagram_type):
    diagram = build_science_diagram(request_text)

    assert diagram is not None
    assert diagram["type"] == diagram_type
    assert validate_diagram_spec(diagram) == diagram
    assert 1 <= len(diagram["objects"]) <= 24


def test_diagram_requires_explicit_intent_and_a_supported_topic():
    assert build_science_diagram("Explain forces on a box") is None
    assert build_science_diagram("Draw a detailed human heart") is None
    assert build_science_diagram(None) is None


def test_validator_rejects_unknown_fields_unsafe_text_and_oversized_shapes():
    valid = build_science_diagram("Draw a force diagram")
    attempts = []

    unknown_field = dict(valid)
    unknown_field["script"] = "alert(1)"
    attempts.append(unknown_field)

    unsafe_label = json.loads(json.dumps(valid))
    unsafe_label["objects"][0]["label"] = "<script>alert(1)</script>"
    attempts.append(unsafe_label)

    outside_canvas = json.loads(json.dumps(valid))
    outside_canvas["objects"][0]["x"] = 90
    outside_canvas["objects"][0]["width"] = 20
    attempts.append(outside_canvas)

    too_many_objects = json.loads(json.dumps(valid))
    too_many_objects["objects"] = [
        {"id": f"item-{index}", "kind": "label", "x": 5, "y": 5,
         "text": "Safe label", "anchor": "start"}
        for index in range(25)
    ]
    attempts.append(too_many_objects)

    for attempt in attempts:
        with pytest.raises(DiagramValidationError):
            validate_diagram_spec(attempt)


def test_database_migrates_and_preserves_diagram_data(tmp_path, monkeypatch):
    db_path = tmp_path / "old-chat.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute("""
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    database.init_db()
    diagram = build_science_diagram("Draw a circuit diagram")
    message_id = database.save_message(
        "science:test",
        "assistant",
        "A circuit explanation.",
        diagram=diagram,
    )

    record = database.get_message_record("science:test", message_id)
    assert record["diagram"] == diagram
    assert database.load_message_records("science:test")[0]["diagram"] == diagram


def _configure_science_route(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "science-chat.db"))
    database.init_db()
    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: {
        "provider": "groq",
        "api_key": "gsk-test-key-that-is-long-enough",
        "model": "openai/gpt-oss-120b",
    })


def test_science_answer_returns_and_restores_a_diagram(monkeypatch, tmp_path):
    _configure_science_route(monkeypatch, tmp_path)
    captured = {}

    def fake_solution(messages, **_kwargs):
        captured["messages"] = messages
        return AIResponse("The arrows show each force.\n\nCONFIDENCE: High", 12, FINISH_REASON_COMPLETE)

    monkeypatch.setattr(app_module, "get_math_solution", fake_solution)
    client = app_module.app.test_client()
    response = client.post("/science/ask", json={"message": "Draw a force diagram for a box"})
    history = client.get("/science/history").get_json()["messages"]

    assert response.status_code == 200
    assert response.get_json()["diagram"]["type"] == "force_diagram"
    assert history[-1]["diagram"] == response.get_json()["diagram"]
    assert any("reviewed local diagram" in message["content"] for message in captured["messages"])
    assert any("Do not output SVG" in message["content"] for message in captured["messages"])


def test_stream_completion_contains_the_saved_diagram(monkeypatch, tmp_path):
    _configure_science_route(monkeypatch, tmp_path)

    def fake_stream(*_args, **_kwargs):
        yield AIStreamEvent(text="Water moves in a cycle.\n\nCONFIDENCE: High")
        yield AIStreamEvent(done=True, tokens_used=9, finish_reason=FINISH_REASON_COMPLETE)

    monkeypatch.setattr(app_module, "get_math_solution_stream", fake_stream)
    client = app_module.app.test_client()
    response = client.post("/science/stream", json={"message": "Draw a water cycle diagram"})
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '"type": "process_diagram"' in body
    assert client.get("/science/history").get_json()["messages"][-1]["diagram"]["title"] == "The water cycle"


def test_broken_saved_diagram_json_does_not_break_history(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "broken-diagram.db"))
    database.init_db()
    message_id = database.save_message("science:test", "assistant", "Text still works.")
    with database.get_connection() as connection:
        connection.execute(
            "UPDATE messages SET diagram_spec = ? WHERE id = ?",
            ("{broken", message_id),
        )

    assert database.load_message_records("science:test")[0]["diagram"] is None
