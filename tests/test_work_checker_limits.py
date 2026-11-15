import multiprocessing
import time

import pytest
import app as app_module
import ai.work_checker as checker
from ai.service import AIResponse, AIStreamEvent


@pytest.mark.parametrize("expression", [
    "2^(20^4)", "2^(-99999999)", "2^(10+20+20)", "((10^20)^20)^20",
    "__import__(os)", "x.__class__",
])
def test_work_parser_rejects_executable_or_excessive_calculations(expression):
    assert checker._parse_safe_expression(expression) is None


@pytest.mark.parametrize("route", ["/ask", "/stream"])
def test_nested_power_does_not_crash_a_chat_or_leak_its_reservation(monkeypatch, route):
    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: {"provider": "groq"})
    monkeypatch.setattr(app_module, "detect_and_solve", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "get_math_solution", lambda *a, **k: AIResponse("Unverified fallback", 0, "complete"))
    def stream(*args, **kwargs):
        yield AIStreamEvent(text="Unverified fallback")
        yield AIStreamEvent(done=True, finish_reason="complete", tokens_used=0)
    monkeypatch.setattr(app_module, "get_math_solution_stream", stream)
    client = app_module.app.test_client()
    chat = client.get("/history").json["session_id"]
    response = client.post(route, json={"message": "Check my work:\nx=2^(20^4)\nx=1"}, buffered=True)
    assert response.status_code == 200
    assert chat not in app_module.CHAT_WRITES_IN_FLIGHT
    assert checker.check_math_work("x=2^(20^4)\nx=1") is None


def _slow_worker(connection, *args):
    time.sleep(30)


def test_work_verification_deadline_terminates_the_worker(monkeypatch):
    before = {p.pid for p in multiprocessing.active_children()}
    monkeypatch.setattr(checker, "_work_check_worker", _slow_worker)
    monkeypatch.setattr(checker, "MAX_WORK_CHECK_SECONDS", 0.1)
    started = time.monotonic()
    assert checker.check_math_work("x=1\nx=1") is None
    assert time.monotonic() - started < 3
    assert {p.pid for p in multiprocessing.active_children()} <= before


def test_intent_detection_does_not_compute_expressions(monkeypatch):
    monkeypatch.setattr(checker, "_parse_safe_expression", lambda *a: pytest.fail("Intent must be lexical"))
    assert checker.looks_like_work_check_request("x=2^(20^8)\nx=1")


def test_failed_work_check_does_not_retry_in_an_unbounded_local_solver(monkeypatch):
    text = "Check my work:\nx=2^(20^4)\nx=1"
    monkeypatch.setattr(app_module, "load_messages", lambda *_: [{"role": "user", "content": text}])
    monkeypatch.setattr(app_module, "detect_and_solve", lambda *a, **k: pytest.fail("Do not retry timed-out or rejected work"))
    messages = app_module._build_messages_for_ai("bounded-work", text, False, True)
    assert not any("VERIFIED LOCAL WORK CHECK" in str(message) for message in messages)


def _text_only_worker(connection, text, conversation, compare):
    assert len(conversation) == 1
    assert set(conversation[0]) == {"content"}
    connection.send(checker.WorkCheckResult("correct", 1))
    connection.close()


def test_worker_receives_reference_text_without_attachment_data(monkeypatch):
    monkeypatch.setattr(checker, "_work_check_worker", _text_only_worker)
    result = checker.check_math_work("x=4", [{"content": "2x=8", "_attachments": [{"data": "x" * 1_000_000}]}])
    assert result.status == "correct"


def test_oversized_work_and_reference_context_do_not_start_a_process(monkeypatch):
    monkeypatch.setattr(checker.multiprocessing, "get_context", lambda *_: pytest.fail("Reject before spawning"))
    assert checker.check_math_work("x" * 2001) is None
    assert checker.check_math_work("x=1", [{"content": "x" * 48_001}]) is None
