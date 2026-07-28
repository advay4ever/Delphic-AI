import pytest

import app as app_module
from ai.prompt import SCIENCE_TUTOR_SYSTEM_PROMPT
from app import (
    _build_messages_for_ai,
    _build_science_messages_for_ai,
    classify_follow_up,
    list_sessions_for_mode,
    science_quiz_context_active,
    session_belongs_to_mode,
    should_redirect_science_math_tooling,
)


CONVERSATION = [
    {"role": "user", "content": "Solve 3x + 5 = 7x"},
    {"role": "assistant", "content": "Subtract 3x from both sides."},
]


@pytest.fixture(autouse=True)
def no_database_side_effects(monkeypatch):
    monkeypatch.setattr(app_module, "load_messages", lambda session_id: [])
    monkeypatch.setattr(app_module, "increment_question_count", lambda session_id: 1)
    monkeypatch.setattr(app_module, "add_topic", lambda session_id, topic: None)
    monkeypatch.setattr(app_module, "get_topics", lambda session_id: [])


def test_detects_5th_grade_language_request_as_simplify():
    assert classify_follow_up("Can you explain it in 5th grade language?", CONVERSATION) == "simplify"


def test_detects_easier_words_request_as_simplify():
    assert classify_follow_up("Use easier words please", CONVERSATION) == "simplify"


def test_step_by_step_mode_adds_interactive_instruction():
    messages = _build_messages_for_ai(
        "test-step-mode-on",
        "Solve 2x + 3 = 11",
        hint_mode=False,
        check_mode=False,
        step_by_step_mode=True,
    )
    system_text = "\n".join(msg["content"] for msg in messages if msg["role"] == "system")

    assert "INTERACTIVE STEP-BY-STEP MODE IS ACTIVE" in system_text
    assert "Do NOT provide the whole solution" in system_text
    assert "Give your full explanation and solution as normal" not in system_text


def test_normal_mode_keeps_full_solution_instruction():
    messages = _build_messages_for_ai(
        "test-step-mode-off",
        "Solve 2x + 3 = 11",
        hint_mode=False,
        check_mode=False,
        step_by_step_mode=False,
    )
    system_text = "\n".join(msg["content"] for msg in messages if msg["role"] == "system")

    assert "INTERACTIVE STEP-BY-STEP MODE IS ACTIVE" not in system_text
    assert "Give your full explanation and solution as normal" in system_text


def test_practice_mode_adds_generator_instruction():
    messages = _build_messages_for_ai(
        "test-practice-mode",
        "Give me a similar practice problem.",
        hint_mode=False,
        check_mode=False,
        step_by_step_mode=False,
        practice_mode=True,
    )
    system_text = "\n".join(msg["content"] for msg in messages if msg["role"] == "system")

    assert "PRACTICE PROBLEM GENERATOR MODE IS ACTIVE" in system_text
    assert "Do NOT solve the practice problem" in system_text
    assert "Only provide the new practice problem" in system_text
    assert "Give your full explanation and solution as normal" not in system_text


def test_practice_mode_forces_english_response():
    messages = _build_messages_for_ai(
        "test-practice-mode-english",
        "Give me a similar practice problem.",
        hint_mode=False,
        check_mode=False,
        step_by_step_mode=False,
        practice_mode=True,
    )
    system_text = "\n".join(msg["content"] for msg in messages if msg["role"] == "system")

    assert "Respond in English" in system_text
    assert "LANGUAGE PRESERVATION" not in system_text


def test_science_practice_mode_uses_science_instruction():
    messages = _build_science_messages_for_ai(
        "science:test-practice-mode",
        "Give me a practice question about ecosystems.",
        step_by_step_mode=False,
        practice_mode=True,
    )
    system_text = "\n".join(msg["content"] for msg in messages if msg["role"] == "system")

    assert "SCIENCE PRACTICE MODE IS ACTIVE" in system_text
    assert "Do NOT answer the practice question yet" in system_text
    assert "PRACTICE PROBLEM GENERATOR MODE IS ACTIVE" not in system_text
    assert "SymPy" not in system_text


def test_science_guided_mode_uses_science_instruction():
    messages = _build_science_messages_for_ai(
        "science:test-guided-mode",
        "Explain photosynthesis",
        step_by_step_mode=True,
        practice_mode=False,
    )
    system_text = "\n".join(msg["content"] for msg in messages if msg["role"] == "system")

    assert "SCIENCE GUIDED MODE IS ACTIVE" in system_text
    assert "next reasoning step" in system_text
    assert "final sentence must be a question" in system_text
    assert "INTERACTIVE STEP-BY-STEP MODE IS ACTIVE" not in system_text


def test_science_quiz_mode_uses_quiz_instruction():
    messages = _build_science_messages_for_ai(
        "science:test-quiz-mode",
        "Start a quiz about ecosystems",
        quiz_mode=True,
    )
    system_text = "\n".join(msg["content"] for msg in messages if msg["role"] == "system")

    assert "SCIENCE QUIZ MODE IS ACTIVE" in system_text
    assert "5-question science quiz" in system_text
    assert "ask Question 1 only" in system_text
    assert "Do NOT include answers" in system_text
    assert "If the student's answer is partly correct or wrong, explain exactly why" in system_text


def test_science_quiz_context_detects_active_quiz():
    conversation = [
        {"role": "assistant", "content": "Science quiz starting. Question 1: What do plants need for photosynthesis?"},
        {"role": "user", "content": "Sunlight"},
    ]

    assert science_quiz_context_active(conversation)


def test_science_quiz_context_stops_after_final_score():
    conversation = [
        {"role": "assistant", "content": "Final score: 4/5. Quiz complete."},
    ]

    assert not science_quiz_context_active(conversation)


def test_science_quiz_continuation_adds_grading_instruction(monkeypatch):
    monkeypatch.setattr(app_module, "load_messages", lambda session_id: [
        {"role": "assistant", "content": "Science quiz starting. Question 1: What is erosion?"},
        {"role": "user", "content": "When rocks move away"},
    ])

    messages = _build_science_messages_for_ai(
        "science:test-quiz-continuation",
        "When rocks move away",
    )
    system_text = "\n".join(msg["content"] for msg in messages if msg["role"] == "system")

    assert "SCIENCE QUIZ CONTINUATION MODE IS ACTIVE" in system_text
    assert "Do not restart the quiz" in system_text
    assert "If the student's answer is correct, mark it correct" in system_text
    assert "ask the next quiz question only" in system_text


def test_science_quiz_continuation_includes_earth_layer_accuracy_guard(monkeypatch):
    monkeypatch.setattr(app_module, "load_messages", lambda session_id: [
        {"role": "assistant", "content": "Question 2: Which layer is directly below the crust?"},
    ])

    messages = _build_science_messages_for_ai(
        "science:test-earth-layer-quiz",
        "mantle",
    )
    system_text = "\n".join(msg["content"] for msg in messages if msg["role"] == "system")

    assert "The layer directly below the crust is the mantle" in system_text
    assert "crust, mantle, outer core, inner core" in system_text


def test_session_mode_filtering():
    assert session_belongs_to_mode("science:abc", "science")
    assert not session_belongs_to_mode("science:abc", "math")
    assert session_belongs_to_mode("abc", "math")
    assert not session_belongs_to_mode("abc", "science")


def test_list_sessions_for_mode_filters_science_sessions(monkeypatch):
    monkeypatch.setattr(app_module, "list_all_sessions", lambda: [
        {"session_id": "math-1", "preview": "Solve 2x = 4"},
        {"session_id": "science:1", "preview": "Explain photosynthesis"},
    ])

    assert [s["session_id"] for s in list_sessions_for_mode("math")] == ["math-1"]
    assert [s["session_id"] for s in list_sessions_for_mode("science")] == ["science:1"]


def test_science_page_renders():
    client = app_module.app.test_client()
    response = client.get("/science")

    assert response.status_code == 200
    assert b"Delphic Science" in response.data
    assert b'href="/#tutor"' in response.data
    assert b'aria-label="Switch to Math tutor"' in response.data
    assert b'aria-label="Back to home page"' in response.data
    assert b"Connect a formula" in response.data
    assert b"Check my reasoning: a chemical reaction creates new atoms" in response.data
    assert b"Guided Reasoning Mode" in response.data
    assert b"Quiz Mode" in response.data
    assert b"Practice This Concept" in response.data
    assert b"Download Transcript" in response.data
    assert b"Step-by-Step Mode" not in response.data
    assert b"Practice Similar Problem" not in response.data


def test_math_page_links_to_science_workspace():
    client = app_module.app.test_client()
    response = client.get("/")

    assert response.status_code == 200
    assert b'href="/science"' in response.data
    assert b"Math reasoning workspace" in response.data
    assert b'data-start-tutor>Math tutor</button>' in response.data
    assert b"Start learning" not in response.data
    assert b'aria-label="Switch to Science tutor"' in response.data
    assert b'aria-label="Back to home page"' in response.data
    assert b"vendor/katex/katex.min.css" in response.data
    assert b"vendor/marked/marked.umd.js" in response.data
    assert b"cdn.jsdelivr.net" not in response.data


def test_local_app_rejects_untrusted_hosts_and_sets_security_headers():
    client = app_module.app.test_client()

    trusted_response = client.get("/", headers={"Host": "127.0.0.1:5001"})
    untrusted_response = client.get("/", headers={"Host": "attacker.example"})

    assert trusted_response.status_code == 200
    assert trusted_response.headers["X-Content-Type-Options"] == "nosniff"
    assert trusted_response.headers["X-Frame-Options"] == "DENY"
    assert trusted_response.headers["Referrer-Policy"] == "no-referrer"
    assert trusted_response.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert untrusted_response.status_code == 400


def test_science_math_tool_redirect_detector():
    assert should_redirect_science_math_tooling("Graph y = x^2")
    assert should_redirect_science_math_tooling("plot f(x) = x^2 - 4")
    assert not should_redirect_science_math_tooling("What does force mean in physics?")
    assert not should_redirect_science_math_tooling("Explain how temperature changes in this experiment")


def test_ai_settings_saves_provider_without_returning_key():
    app_module.AI_SETTINGS_BY_SESSION.clear()
    client = app_module.app.test_client()

    response = client.post("/ai-settings", json={
        "provider": "groq",
        "api_key": "gsk-test-key-that-is-long-enough",
    })

    data = response.get_json()
    assert response.status_code == 200
    assert data["configured"] is True
    assert data["provider"] == "groq"
    assert "api_key" not in data
    assert "gsk-test-key" not in response.get_data(as_text=True)


def test_ai_settings_rejects_non_ascii_api_key_without_saving_it():
    app_module.AI_SETTINGS_BY_SESSION.clear()
    client = app_module.app.test_client()

    response = client.post("/ai-settings", json={
        "provider": "openai",
        "api_key": "sk-proj-\N{EN DASH}invalid-key",
    })

    assert response.status_code == 400
    assert "unsupported character" in response.get_json()["error"]
    assert app_module.AI_SETTINGS_BY_SESSION == {}


def test_science_ask_uses_science_prompt(monkeypatch):
    captured = {}
    saved_messages = []

    def fake_get_math_solution(messages, system_prompt=None, ai_config=None):
        captured["messages"] = messages
        captured["system_prompt"] = system_prompt
        captured["ai_config"] = ai_config
        return "Science answer\n\nCONFIDENCE: High", 12

    monkeypatch.setattr(app_module, "save_message", lambda session_id, role, content: saved_messages.append((session_id, role, content)))
    monkeypatch.setattr(app_module, "log_tokens", lambda session_id, tokens: None)
    monkeypatch.setattr(app_module, "get_total_tokens", lambda session_id: 12)
    monkeypatch.setattr(app_module, "get_math_solution", fake_get_math_solution)
    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: {
        "provider": "groq",
        "api_key": "gsk-test-key-that-is-long-enough",
        "source": "test",
    })

    client = app_module.app.test_client()
    response = client.post("/science/ask", json={"message": "Explain photosynthesis"})

    assert response.status_code == 200
    assert response.get_json()["reply"] == "Science answer\n\nCONFIDENCE: High"
    assert captured["system_prompt"] == SCIENCE_TUTOR_SYSTEM_PROMPT
    assert captured["ai_config"]["provider"] == "groq"
    assert saved_messages[0][0].startswith("science:")
    assert saved_messages[0][1:] == ("user", "Explain photosynthesis")
    assert saved_messages[1][0].startswith("science:")
    assert saved_messages[1][1:] == ("assistant", "Science answer\n\nCONFIDENCE: High")


def test_science_ask_redirects_graph_requests_without_calling_ai(monkeypatch):
    saved_messages = []

    def fail_get_math_solution(*args, **kwargs):
        raise AssertionError("Science graph redirect should not call the AI service")

    monkeypatch.setattr(app_module, "save_message", lambda session_id, role, content: saved_messages.append((session_id, role, content)))
    monkeypatch.setattr(app_module, "get_total_tokens", lambda session_id: 0)
    monkeypatch.setattr(app_module, "get_math_solution", fail_get_math_solution)

    client = app_module.app.test_client()
    response = client.post("/science/ask", json={"message": "Graph y = x^2"})

    assert response.status_code == 200
    assert "Math tutor" in response.get_json()["reply"]
    assert saved_messages[0][1:] == ("user", "Graph y = x^2")
    assert saved_messages[1][0].startswith("science:")
    assert "graphing request" in saved_messages[1][2]


def test_science_stream_uses_science_prompt(monkeypatch):
    captured = {}
    saved_messages = []

    def fake_get_math_solution_stream(messages, system_prompt=None, ai_config=None):
        captured["messages"] = messages
        captured["system_prompt"] = system_prompt
        captured["ai_config"] = ai_config
        yield "Science stream answer\n\nCONFIDENCE: High", False, 0
        yield "", True, 0

    monkeypatch.setattr(app_module, "save_message", lambda session_id, role, content: saved_messages.append((session_id, role, content)))
    monkeypatch.setattr(app_module, "get_total_tokens", lambda session_id: 0)
    monkeypatch.setattr(app_module, "get_math_solution_stream", fake_get_math_solution_stream)
    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: {
        "provider": "groq",
        "api_key": "gsk-test-key-that-is-long-enough",
        "source": "test",
    })

    client = app_module.app.test_client()
    response = client.post("/science/stream", json={"message": "Explain atoms"})
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "data: Science stream answer" in body
    assert "[DONE:0]" in body
    assert captured["system_prompt"] == SCIENCE_TUTOR_SYSTEM_PROMPT
    assert captured["ai_config"]["provider"] == "groq"
    assert saved_messages[0][0].startswith("science:")
    assert saved_messages[0][1:] == ("user", "Explain atoms")
    assert saved_messages[1][0].startswith("science:")
    assert saved_messages[1][1:] == ("assistant", "Science stream answer\n\nCONFIDENCE: High")


def test_science_stream_redirects_graph_requests_without_calling_ai(monkeypatch):
    saved_messages = []

    def fail_get_math_solution_stream(*args, **kwargs):
        raise AssertionError("Science graph redirect should not call the AI service")

    monkeypatch.setattr(app_module, "save_message", lambda session_id, role, content: saved_messages.append((session_id, role, content)))
    monkeypatch.setattr(app_module, "get_total_tokens", lambda session_id: 0)
    monkeypatch.setattr(app_module, "get_math_solution_stream", fail_get_math_solution_stream)

    client = app_module.app.test_client()
    response = client.post("/science/stream", json={"message": "Graph y = x^2"})
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "data: Math" in body
    assert "data: tutor" in body
    assert "[DONE:0]" in body
    assert saved_messages[0][1:] == ("user", "Graph y = x^2")
    assert saved_messages[1][0].startswith("science:")
    assert "graphing request" in saved_messages[1][2]


def test_math_session_switch_rejects_science_session():
    client = app_module.app.test_client()
    response = client.post("/sessions/switch", json={"session_id": "science:abc"})

    assert response.status_code == 400
    assert response.get_json()["error"] == "Session does not belong to the math tutor."
