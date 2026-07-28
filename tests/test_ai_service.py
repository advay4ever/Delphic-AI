import pytest
import httpx

from flask import Flask

from desktop_launcher import start_local_server

from ai.service import (
    SUPPORTED_AI_PROVIDERS,
    get_api_key_validation_error,
    get_chat_completion_options,
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


def test_openai_compatible_providers_keep_max_tokens():
    for provider_id in ("groq", "google", "mistral", "together", "xai", "deepseek"):
        options = get_chat_completion_options(
            SUPPORTED_AI_PROVIDERS[provider_id],
            temperature=0.3,
            max_tokens=2048,
        )

        assert options["max_tokens"] == 2048
        assert options["temperature"] == 0.3
        assert "max_completion_tokens" not in options


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


def test_desktop_server_runs_without_blocking_the_launcher():
    test_app = Flask(__name__)

    @test_app.get("/health")
    def health():
        return {"status": "ok"}

    server, thread = start_local_server(test_app, port=0)
    try:
        response = httpx.get(f"http://127.0.0.1:{server.server_port}/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    finally:
        server.shutdown()
        thread.join(timeout=2)
