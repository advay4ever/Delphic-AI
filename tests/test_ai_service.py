import pytest
import threading
from types import SimpleNamespace

from flask import Flask

import ai.service as service
import desktop_launcher

from ai.service import (
    AI_PROVIDER_ERROR_MESSAGE,
    AIResponse,
    AIStreamEvent,
    FINISH_REASON_COMPLETE,
    FINISH_REASON_CONTENT_FILTER,
    FINISH_REASON_ERROR,
    FINISH_REASON_LENGTH,
    FINISH_REASON_TOOL_STOP,
    FINISH_REASON_UNKNOWN,
    EXTRACTION_MAX_OUTPUT_TOKENS,
    SUPPORTED_AI_PROVIDERS,
    TUTOR_MAX_OUTPUT_TOKENS,
    get_math_solution,
    get_api_key_validation_error,
    get_chat_completion_options,
    get_model_validation_error,
    get_stream_usage_total,
    normalize_finish_reason,
    resolve_ai_config,
)


def test_openai_uses_max_completion_tokens():
    options = get_chat_completion_options(
        SUPPORTED_AI_PROVIDERS["openai"],
        temperature=0.3,
        max_tokens=2048,
    )

    assert options["max_completion_tokens"] == 2048
    assert "max_tokens" not in options
    assert "temperature" not in options


def test_openai_uses_default_temperature_for_equation_extraction():
    options = get_chat_completion_options(
        SUPPORTED_AI_PROVIDERS["openai"],
        temperature=0.0,
        max_tokens=100,
    )

    assert options == {"max_completion_tokens": 100}


def test_openai_compatible_providers_keep_max_tokens_and_temperature_when_supported():
    for provider_id in ("groq", "mistral", "together", "xai", "deepseek"):
        options = get_chat_completion_options(
            SUPPORTED_AI_PROVIDERS[provider_id],
            temperature=0.3,
            max_tokens=2048,
        )

        assert options["max_tokens"] == 2048
        assert options["temperature"] == 0.3
        assert "max_completion_tokens" not in options


def test_google_omits_temperature_for_newer_gemini_models():
    options = get_chat_completion_options(
        SUPPORTED_AI_PROVIDERS["google"],
        temperature=0.3,
        max_tokens=2048,
    )

    assert options == {"max_tokens": 2048}


def test_stream_usage_uses_a_provider_total_or_combines_input_and_output_tokens():
    assert get_stream_usage_total({"total_tokens": 12, "input_tokens": 4, "output_tokens": 8}) == 12
    assert get_stream_usage_total({"prompt_tokens": 4, "completion_tokens": 8}) == 12
    assert get_stream_usage_total(None) == 0


@pytest.mark.parametrize(
    ("provider_reason", "expected"),
    [
        ("stop", FINISH_REASON_COMPLETE),
        ("end_turn", FINISH_REASON_COMPLETE),
        ("length", FINISH_REASON_LENGTH),
        ("max_tokens", FINISH_REASON_LENGTH),
        ("content_filter", FINISH_REASON_CONTENT_FILTER),
        ("tool_calls", FINISH_REASON_TOOL_STOP),
        ("FinishReason.STOP", FINISH_REASON_COMPLETE),
        ("something-new", FINISH_REASON_UNKNOWN),
        (None, FINISH_REASON_UNKNOWN),
    ],
)
def test_provider_finish_reasons_are_normalized(provider_reason, expected):
    assert normalize_finish_reason(provider_reason) == expected


def test_openai_stream_requests_usage_and_handles_the_final_usage_only_chunk(monkeypatch):
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return iter([
                SimpleNamespace(
                    choices=[SimpleNamespace(
                        delta=SimpleNamespace(content="A tutor answer."),
                        finish_reason=None,
                    )],
                    usage=None,
                ),
                SimpleNamespace(
                    choices=[SimpleNamespace(
                        delta=SimpleNamespace(content=None),
                        finish_reason="length",
                    )],
                    usage=None,
                ),
                SimpleNamespace(
                    choices=[],
                    usage=SimpleNamespace(total_tokens=23),
                ),
            ])

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    monkeypatch.setattr(service, "create_ai_client", lambda _config: (fake_client, "gpt-5.6-luna"))

    chunks = list(service.get_math_solution_stream([], ai_config={
        "provider": "openai",
        "api_key": "sk-test-key-that-is-long-enough",
        "model": "gpt-5.6-luna",
    }))

    assert chunks == [
        AIStreamEvent(text="A tutor answer."),
        AIStreamEvent(done=True, tokens_used=23, finish_reason=FINISH_REASON_LENGTH),
    ]
    assert captured["stream_options"] == {"include_usage": True}
    assert captured["max_completion_tokens"] == TUTOR_MAX_OUTPUT_TOKENS


def test_openai_non_streaming_response_includes_finish_reason(monkeypatch):
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(
                    message=SimpleNamespace(content="A complete answer."),
                    finish_reason="stop",
                )],
                usage=SimpleNamespace(total_tokens=19),
            )

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    monkeypatch.setattr(service, "create_ai_client", lambda _config: (fake_client, "test-model"))

    response = get_math_solution([], ai_config={
        "provider": "groq",
        "api_key": "gsk-test-key-that-is-long-enough",
        "model": "openai/gpt-oss-120b",
    })

    assert response == AIResponse(
        text="A complete answer.",
        tokens_used=19,
        finish_reason=FINISH_REASON_COMPLETE,
    )
    assert captured["max_tokens"] == TUTOR_MAX_OUTPUT_TOKENS


def test_equation_extraction_keeps_its_small_output_limit(monkeypatch):
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="2*x + 3 = 11"))],
            )

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    monkeypatch.setattr(service, "create_ai_client", lambda _config: (fake_client, "test-model"))

    result = service.extract_equation("Solve 2x + 3 = 11", ai_config={
        "provider": "groq",
        "api_key": "gsk-test-key-that-is-long-enough",
        "model": "openai/gpt-oss-120b",
    })

    assert result == "2*x + 3 = 11"
    assert captured["max_tokens"] == EXTRACTION_MAX_OUTPUT_TOKENS


def test_anthropic_non_streaming_response_includes_stop_reason(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "content": [{"type": "text", "text": "A partial answer."}],
                "usage": {"input_tokens": 8, "output_tokens": 12},
                "stop_reason": "max_tokens",
            }

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def post(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr(service.httpx, "Client", lambda **_kwargs: FakeClient())

    response = service.get_anthropic_solution(
        [{"role": "user", "content": "Explain this."}],
        {"api_key": "anthropic-test-key", "model": "claude-haiku-4-5-20251001"},
        SUPPORTED_AI_PROVIDERS["anthropic"],
        temperature=0.3,
        max_tokens=2048,
    )

    assert response == AIResponse(
        text="A partial answer.",
        tokens_used=20,
        finish_reason=FINISH_REASON_LENGTH,
    )


def test_anthropic_stream_includes_stop_reason_and_usage(monkeypatch):
    events = [
        {"type": "message_start", "message": {"usage": {"input_tokens": 7}}},
        {"type": "content_block_delta", "delta": {"text": "Streaming answer."}},
        {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn"},
            "usage": {"output_tokens": 9},
        },
    ]

    class FakeStreamResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def raise_for_status(self):
            return None

        def iter_text(self):
            return iter([f"data: {service.json.dumps(event)}\n\n" for event in events])

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def stream(self, *_args, **_kwargs):
            return FakeStreamResponse()

    monkeypatch.setattr(service.httpx, "Client", lambda **_kwargs: FakeClient())

    result = list(service.stream_anthropic_solution(
        [{"role": "user", "content": "Explain this."}],
        {"api_key": "anthropic-test-key", "model": "claude-haiku-4-5-20251001"},
        SUPPORTED_AI_PROVIDERS["anthropic"],
        temperature=0.3,
        max_tokens=2048,
    ))

    assert result == [
        AIStreamEvent(text="Streaming answer."),
        AIStreamEvent(done=True, tokens_used=16, finish_reason=FINISH_REASON_COMPLETE),
    ]


def test_anthropic_stream_error_becomes_a_safe_error_event(monkeypatch):
    class FakeStreamResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def raise_for_status(self):
            return None

        def iter_text(self):
            return iter(['data: {"type": "error", "error": {"message": "private detail"}}\n\n'])

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def stream(self, *_args, **_kwargs):
            return FakeStreamResponse()

    monkeypatch.setattr(service.httpx, "Client", lambda **_kwargs: FakeClient())

    result = list(service.get_math_solution_stream([], ai_config={
        "provider": "anthropic",
        "api_key": "anthropic-test-key",
        "model": "claude-haiku-4-5-20251001",
    }))

    assert result == [AIStreamEvent(
        text=AI_PROVIDER_ERROR_MESSAGE,
        done=True,
        finish_reason=FINISH_REASON_ERROR,
    )]
    assert "private detail" not in result[0].text


def test_provider_errors_are_logged_but_not_shown_to_students(monkeypatch):
    def raise_provider_error(_config):
        raise RuntimeError("provider detail that must stay private")

    monkeypatch.setattr(service, "create_ai_client", raise_provider_error)

    response = get_math_solution([], ai_config={
        "provider": "groq",
        "api_key": "gsk-test-key-that-is-long-enough",
        "model": "openai/gpt-oss-120b",
    })

    assert response.text == AI_PROVIDER_ERROR_MESSAGE
    assert "provider detail" not in response.text
    assert response.tokens_used == 0
    assert response.finish_reason == FINISH_REASON_ERROR


def test_streaming_provider_errors_are_not_shown_to_students(monkeypatch):
    def raise_provider_error(_config):
        raise RuntimeError("provider detail that must stay private")

    monkeypatch.setattr(service, "create_ai_client", raise_provider_error)

    chunks = list(service.get_math_solution_stream([], ai_config={
        "provider": "groq",
        "api_key": "gsk-test-key-that-is-long-enough",
        "model": "openai/gpt-oss-120b",
    }))

    assert chunks == [AIStreamEvent(
        text=AI_PROVIDER_ERROR_MESSAGE,
        done=True,
        finish_reason=FINISH_REASON_ERROR,
    )]


def test_api_key_validation_rejects_non_ascii_characters():
    error = get_api_key_validation_error("sk-proj-\N{EN DASH}invalid-key")

    assert "unsupported character" in error


def test_api_key_validation_rejects_internal_whitespace():
    error = get_api_key_validation_error("sk-proj-invalid key")

    assert "space or line break" in error


def test_resolve_ai_config_rejects_invalid_key_before_creating_client():
    with pytest.raises(ValueError, match="unsupported character"):
        resolve_ai_config({
            "provider": "openai",
            "api_key": "sk-proj-\N{EN DASH}invalid-key",
        })


def test_resolve_ai_config_keeps_a_selected_model():
    config, _provider = resolve_ai_config({
        "provider": "groq",
        "api_key": "gsk-test-key-that-is-long-enough",
        "model": "llama-3.1-8b-instant",
    })

    assert config["model"] == "llama-3.1-8b-instant"


def test_model_validation_rejects_malformed_model_ids():
    assert get_model_validation_error("model name with spaces") == "Choose a valid model ID."


def test_model_validation_rejects_models_not_listed_for_the_provider():
    assert get_model_validation_error("gpt-5.2", "groq") == "Choose one of the listed models."


def test_anthropic_model_list_includes_current_fast_and_reasoning_choices():
    model_ids = {model["id"] for model in SUPPORTED_AI_PROVIDERS["anthropic"]["models"]}

    assert "claude-haiku-4-5-20251001" in model_ids
    assert "claude-sonnet-5" in model_ids
    assert "claude-opus-5" in model_ids
    assert "claude-fable-5" in model_ids
    assert "claude-opus-4-1-20250805" not in model_ids


def test_openai_model_list_includes_fast_and_reasoning_choices():
    model_ids = {model["id"] for model in SUPPORTED_AI_PROVIDERS["openai"]["models"]}

    assert "gpt-5.6-luna" in model_ids
    assert "gpt-5.6-terra" in model_ids
    assert "gpt-5.6-sol" in model_ids
    assert "gpt-5.5" in model_ids
    assert "gpt-5" in model_ids
    assert "gpt-5-mini" in model_ids
    assert "gpt-5-nano" in model_ids
    assert "gpt-4.1" in model_ids


def test_desktop_server_runs_without_blocking_the_launcher(monkeypatch):
    test_app = Flask(__name__)
    started = threading.Event()
    stopped = threading.Event()

    class FakeServer:
        def serve_forever(self):
            started.set()
            stopped.wait(timeout=2)

        def shutdown(self):
            stopped.set()

    fake_server = FakeServer()
    monkeypatch.setattr(desktop_launcher, "BoundedDesktopServer", lambda *_args, **_kwargs: fake_server)

    server, thread = desktop_launcher.start_local_server(test_app, port=0)
    try:
        assert server is fake_server
        assert started.wait(timeout=1)
        assert thread.is_alive()
    finally:
        server.shutdown()
        thread.join(timeout=2)
