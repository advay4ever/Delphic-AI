import multiprocessing
import time

import pytest

import ai.detector as detector
import ai.math_tools as math_tools


def _slow_worker(connection, *args):
    time.sleep(30)


def _crashed_worker(connection, *args):
    connection.close()


@pytest.mark.parametrize("tool", [math_tools.solve_equation, math_tools.simplify_expression,
                                  math_tools.differentiate, math_tools.integrate_expr,
                                  math_tools.factor_expression])
def test_calculation_deadline_stops_and_reaps_the_worker(monkeypatch, tool):
    before = {child.pid for child in multiprocessing.active_children()}
    monkeypatch.setattr(math_tools, "_calculation_worker", _slow_worker)
    monkeypatch.setattr(math_tools, "MAX_CALCULATION_SECONDS", 0.1)
    started = time.monotonic()
    result = tool("x^2")
    assert result["success"] is False
    assert result["error_code"] == "timeout"
    assert time.monotonic() - started < 3
    assert {child.pid for child in multiprocessing.active_children()} <= before


def test_worker_exit_without_a_result_is_not_verification(monkeypatch):
    monkeypatch.setattr(math_tools, "_calculation_worker", _crashed_worker)
    assert math_tools.simplify_expression("2+2")["success"] is False


def test_oversized_input_is_rejected_before_spawning(monkeypatch):
    monkeypatch.setattr(math_tools.multiprocessing, "get_context", lambda *args: pytest.fail("Do not spawn"))
    assert math_tools.integrate_expr("x" * 2000)["success"] is False


@pytest.mark.parametrize("prompt,operation", [
    ("Solve x^2=1", "solve_equation"), ("Simplify x^2", "simplify_expression"),
    ("Factor x^2-1", "factor_expression"), ("Differentiate x^2", "differentiate"),
    ("Integrate x^2", "integrate_expr"),
])
def test_timeout_does_not_retry_using_ai_extraction(monkeypatch, prompt, operation):
    monkeypatch.setattr(detector, operation, lambda *a, **k: {"success": False, "error_code": "timeout"})
    monkeypatch.setattr(detector, "extract_equation", lambda *a, **k: pytest.fail("Do not retry timed-out work"))
    assert detector.detect_and_solve(prompt) is None


def test_expensive_supported_integral_has_a_hard_deadline(monkeypatch):
    monkeypatch.setattr(math_tools, "MAX_CALCULATION_SECONDS", 0.5)
    started = time.monotonic()
    result = math_tools.integrate_expr("x^32/(x^32+1)")
    assert result["success"] is False
    assert result["error_code"] == "timeout"
    assert time.monotonic() - started < 3


def test_failed_process_start_is_a_safe_failure(monkeypatch):
    def unavailable(*args):
        raise OSError("review-only unavailable worker")
    monkeypatch.setattr(math_tools.multiprocessing, "get_context", unavailable)
    result = math_tools.solve_equation("x=2")
    assert result["success"] is False
    assert "review-only" not in result["error"]
