"""
Delphic AI - AI Service
"""

import json
import logging
import re
import time
from dataclasses import dataclass

import httpx
from openai import OpenAI
from ai.attachments import prepare_provider_messages
from ai.prompt import (
    ANTHROPIC_API_KEY,
    DEEPSEEK_API_KEY,
    GOOGLE_API_KEY,
    GROQ_API_KEY,
    MISTRAL_API_KEY,
    OPENAI_API_KEY,
    OPENROUTER_API_KEY,
    TOGETHER_API_KEY,
    XAI_API_KEY,
    MATH_TUTOR_SYSTEM_PROMPT,
)


logger = logging.getLogger(__name__)
AI_PROVIDER_ERROR_MESSAGE = (
    "Sorry, I couldn't reach the selected AI provider. "
    "Check your API key, model, and internet connection, then try again."
)

FINISH_REASON_COMPLETE = "complete"
FINISH_REASON_LENGTH = "length"
FINISH_REASON_CONTENT_FILTER = "content_filter"
FINISH_REASON_TOOL_STOP = "tool_stop"
FINISH_REASON_ERROR = "error"
FINISH_REASON_UNKNOWN = "unknown"
TUTOR_MAX_OUTPUT_TOKENS = 4096
EXTRACTION_MAX_OUTPUT_TOKENS = 100
MAX_CONTINUATIONS_PER_ANSWER = 1
ANTHROPIC_STREAM_TIMEOUT = httpx.Timeout(60.0, connect=10.0, write=15.0, pool=10.0)
ANTHROPIC_STREAM_WINDOW_SECONDS = 180.0


@dataclass(frozen=True)
class AIResponse:
    """One finished provider response and the metadata Delphic needs."""

    text: str
    tokens_used: int
    finish_reason: str


@dataclass(frozen=True)
class AIStreamEvent:
    """One text or completion event from a streamed provider response."""

    text: str = ""
    done: bool = False
    tokens_used: int = 0
    finish_reason: str | None = None


def normalize_finish_reason(reason: object) -> str:
    """Convert provider-specific stop reasons into Delphic's small shared set."""
    if reason is None:
        return FINISH_REASON_UNKNOWN

    clean_reason = str(reason).strip().lower().rsplit(".", 1)[-1]
    if clean_reason in {
        "stop", "stopped", "complete", "completed", "end_turn", "stop_sequence", "eos",
    }:
        return FINISH_REASON_COMPLETE
    if clean_reason in {
        "length", "max_tokens", "max_output_tokens", "max_completion_tokens", "model_length",
    }:
        return FINISH_REASON_LENGTH
    if clean_reason in {
        "content_filter", "content_filtered", "safety", "blocked", "refusal",
    }:
        return FINISH_REASON_CONTENT_FILTER
    if clean_reason in {
        "tool_calls", "tool_use", "function_call", "pause_turn", "tool_stop",
    }:
        return FINISH_REASON_TOOL_STOP
    if clean_reason in {"error", "failed", "failure"}:
        return FINISH_REASON_ERROR
    return FINISH_REASON_UNKNOWN


def get_safe_output_limit(provider: dict, requested_limit: int) -> int:
    """Respect Delphic's limit and any smaller limit set for a provider."""
    provider_limit = provider.get("max_output_tokens")
    if isinstance(provider_limit, int) and provider_limit > 0:
        return min(requested_limit, provider_limit)
    return requested_limit


SUPPORTED_AI_PROVIDERS = {
    "groq": {
        "label": "Groq",
        "client": "openai_compatible",
        "base_url": "https://api.groq.com/openai/v1",
        "model": "openai/gpt-oss-120b",
        "models": [
            {"id": "openai/gpt-oss-120b", "label": "GPT-OSS 120B (recommended)"},
            {"id": "openai/gpt-oss-20b", "label": "GPT-OSS 20B"},
            {"id": "llama-3.3-70b-versatile", "label": "Llama 3.3 70B"},
            {"id": "llama-3.1-8b-instant", "label": "Llama 3.1 8B (fast)"},
        ],
        "env_key": GROQ_API_KEY,
    },
    "openai": {
        "label": "OpenAI",
        "client": "openai_compatible",
        "base_url": None,
        "model": "gpt-5.6-luna",
        "models": [
            {"id": "gpt-5.6-luna", "label": "GPT-5.6 Luna (recommended)"},
            {"id": "gpt-5.6-terra", "label": "GPT-5.6 Terra (balanced)"},
            {"id": "gpt-5.6-sol", "label": "GPT-5.6 Sol (most capable)"},
            {"id": "gpt-5.5", "label": "GPT-5.5 (strong all-purpose)"},
            {"id": "gpt-5.2", "label": "GPT-5.2 (strong reasoning)"},
            {"id": "gpt-5", "label": "GPT-5 (strong reasoning)"},
            {"id": "gpt-5-mini", "label": "GPT-5 mini (fast and affordable)"},
            {"id": "gpt-5-nano", "label": "GPT-5 nano (fastest)"},
            {"id": "gpt-4.1", "label": "GPT-4.1 (strong all-purpose)"},
        ],
        "token_limit_parameter": "max_completion_tokens",
        "supports_temperature": False,
        "supports_stream_usage": True,
        "env_key": OPENAI_API_KEY,
    },
    "openrouter": {
        "label": "OpenRouter",
        "client": "openai_compatible",
        "base_url": "https://openrouter.ai/api/v1",
        "model": "openai/gpt-5.6-terra",
        "models": [
            {"id": "openai/gpt-5.6-terra", "label": "GPT-5.6 Terra (recommended)"},
        ],
        "token_limit_parameter": "max_completion_tokens",
        "supports_temperature": False,
        "supports_stream_usage": True,
        "env_key": OPENROUTER_API_KEY,
    },
    "anthropic": {
        "label": "Anthropic",
        "client": "anthropic",
        "base_url": "https://api.anthropic.com/v1/messages",
        "model": "claude-haiku-4-5-20251001",
        "supports_temperature": False,
        "models": [
            {"id": "claude-haiku-4-5-20251001", "label": "Claude Haiku 4.5 (recommended: fast)"},
            {"id": "claude-sonnet-5", "label": "Claude Sonnet 5 (balanced)"},
            {"id": "claude-opus-5", "label": "Claude Opus 5 (advanced reasoning)"},
            {"id": "claude-fable-5", "label": "Claude Fable 5 (long-running work)"},
        ],
        "env_key": ANTHROPIC_API_KEY,
    },
    "google": {
        "label": "Google Gemini",
        "client": "openai_compatible",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-3.5-flash",
        "supports_temperature": False,
        "models": [
            {"id": "gemini-3.5-flash", "label": "Gemini 3.5 Flash (recommended)"},
            {"id": "gemini-3.6-flash", "label": "Gemini 3.6 Flash"},
        ],
        "env_key": GOOGLE_API_KEY,
    },
    "mistral": {
        "label": "Mistral",
        "client": "openai_compatible",
        "base_url": "https://api.mistral.ai/v1",
        "model": "magistral-small-latest",
        "models": [
            {"id": "magistral-small-latest", "label": "Magistral Small (recommended)"},
        ],
        "env_key": MISTRAL_API_KEY,
    },
    "together": {
        "label": "Together AI",
        "client": "openai_compatible",
        "base_url": "https://api.together.ai/v1",
        "model": "openai/gpt-oss-120b",
        "models": [
            {"id": "openai/gpt-oss-120b", "label": "GPT-OSS 120B (recommended)"},
        ],
        "env_key": TOGETHER_API_KEY,
    },
    "xai": {
        "label": "xAI",
        "client": "openai_compatible",
        "base_url": "https://api.x.ai/v1",
        "model": "grok-4.20-0309-reasoning",
        "models": [
            {"id": "grok-4.20-0309-reasoning", "label": "Grok 4.20 Reasoning (recommended)"},
        ],
        "env_key": XAI_API_KEY,
    },
    "deepseek": {
        "label": "DeepSeek",
        "client": "openai_compatible",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-pro",
        "models": [
            {"id": "deepseek-v4-pro", "label": "DeepSeek V4 Pro (recommended)"},
        ],
        "env_key": DEEPSEEK_API_KEY,
    },
}


def get_api_key_validation_error(api_key: str | None) -> str | None:
    clean_key = str(api_key or "").strip()
    if not clean_key:
        return "Paste a full API key."
    if not clean_key.isascii():
        return (
            "The API key contains an unsupported character. "
            "Copy the key directly from your provider's dashboard and paste it again."
        )
    if any(character.isspace() for character in clean_key):
        return (
            "The API key contains a space or line break. "
            "Copy the key directly from your provider's dashboard and paste it again."
        )

    placeholders = {
        "your-groq-api-key-here",
        "your-real-key-here",
        "gsk-your-key-here",
        "change-me-in-development",
        "your-openai-api-key-here",
        "your-anthropic-api-key-here",
        "your-google-api-key-here",
        "your-mistral-api-key-here",
        "your-together-api-key-here",
        "your-xai-api-key-here",
        "your-deepseek-api-key-here",
        "your-openrouter-api-key-here",
    }
    if len(clean_key) < 12 or clean_key in placeholders or clean_key.startswith("your-"):
        return "Paste a full API key."
    return None


def looks_like_real_api_key(api_key: str | None) -> bool:
    return get_api_key_validation_error(api_key) is None


def get_model_validation_error(model: str | None, provider_id: str | None = None) -> str | None:
    """Accept only well-formed model IDs offered by the selected provider."""
    clean_model = str(model or "").strip()
    if not clean_model:
        return "Choose a model."
    if len(clean_model) > 200 or not re.fullmatch(r"[A-Za-z0-9._:/@-]+", clean_model):
        return "Choose a valid model ID."
    if provider_id:
        provider = SUPPORTED_AI_PROVIDERS.get(provider_id)
        allowed_models = {item["id"] for item in (provider or {}).get("models", [])}
        if clean_model not in allowed_models:
            return "Choose one of the listed models."
    return None


def get_public_provider_options() -> list[dict]:
    """Return provider options without exposing API keys."""
    return [
        {
            "id": provider_id,
            "label": config["label"],
            "model": config["model"],
            "models": config.get("models", []),
        }
        for provider_id, config in SUPPORTED_AI_PROVIDERS.items()
    ]


def get_default_provider_config() -> dict | None:
    """Use environment keys as a fallback for local development."""
    for provider_id in SUPPORTED_AI_PROVIDERS:
        config = SUPPORTED_AI_PROVIDERS[provider_id]
        if looks_like_real_api_key(config["env_key"]):
            return {
                "provider": provider_id,
                "api_key": config["env_key"],
                "model": config["model"],
                "source": "env",
            }
    return None


def resolve_ai_config(ai_config: dict | None = None) -> tuple[dict, dict]:
    config = ai_config or get_default_provider_config()
    if not config or not config.get("api_key"):
        raise ValueError("Add an AI provider and API key before asking the tutor questions.")

    api_key = str(config["api_key"]).strip()
    validation_error = get_api_key_validation_error(api_key)
    if validation_error:
        raise ValueError(validation_error)

    provider_id = config.get("provider", "groq")
    provider = SUPPORTED_AI_PROVIDERS.get(provider_id)
    if provider is None:
        raise ValueError("Choose a supported AI provider.")
    model = str(config.get("model") or provider["model"]).strip()
    model_error = get_model_validation_error(model, provider_id)
    if model_error:
        raise ValueError(model_error)
    return {**config, "api_key": api_key, "model": model}, provider


def create_ai_client(ai_config: dict | None = None) -> tuple[OpenAI, str]:
    config, provider = resolve_ai_config(ai_config)
    kwargs = {"api_key": config["api_key"]}
    if provider["base_url"]:
        kwargs["base_url"] = provider["base_url"]
    return OpenAI(**kwargs), config["model"]


def get_chat_completion_options(provider: dict, temperature: float, max_tokens: int) -> dict:
    """Build provider-specific Chat Completions options."""
    token_limit_parameter = provider.get("token_limit_parameter", "max_tokens")
    options = {token_limit_parameter: max_tokens}
    if provider.get("supports_temperature", True):
        options["temperature"] = temperature
    return options


def get_stream_usage_total(usage: object) -> int:
    """Read a provider's final streamed usage object without guessing token counts."""
    if usage is None:
        return 0
    if isinstance(usage, dict):
        total = usage.get("total_tokens")
        input_tokens = usage.get("input_tokens", usage.get("prompt_tokens", 0))
        output_tokens = usage.get("output_tokens", usage.get("completion_tokens", 0))
    else:
        total = getattr(usage, "total_tokens", None)
        input_tokens = getattr(usage, "input_tokens", getattr(usage, "prompt_tokens", 0))
        output_tokens = getattr(usage, "output_tokens", getattr(usage, "completion_tokens", 0))
    try:
        return int(total) if total is not None else int(input_tokens or 0) + int(output_tokens or 0)
    except (TypeError, ValueError):
        return 0


def split_anthropic_messages(messages: list[dict]) -> tuple[str, list[dict]]:
    system_parts = []
    anthropic_messages = []
    for message in messages:
        role = message.get("role")
        content = message.get("content", "")
        if role == "system":
            system_parts.append(str(content))
        elif role in {"user", "assistant"}:
            anthropic_messages.append({"role": role, "content": content})

    if not anthropic_messages:
        anthropic_messages.append({"role": "user", "content": ""})
    return "\n\n".join(system_parts), anthropic_messages


def get_anthropic_headers(api_key: str) -> dict:
    return {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }


def get_anthropic_solution(
    messages: list[dict],
    api_config: dict,
    provider: dict,
    temperature: float,
    max_tokens: int,
) -> AIResponse:
    system_prompt, anthropic_messages = split_anthropic_messages(messages)
    payload = {
        "model": api_config["model"],
        "messages": anthropic_messages,
        "max_tokens": max_tokens,
    }
    if provider.get("supports_temperature", True):
        payload["temperature"] = temperature
    if system_prompt:
        payload["system"] = system_prompt

    with httpx.Client(timeout=90.0) as client:
        response = client.post(
            provider["base_url"],
            headers=get_anthropic_headers(api_config["api_key"]),
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    reply = "".join(
        block.get("text", "")
        for block in data.get("content", [])
        if block.get("type") == "text"
    )
    usage = data.get("usage", {})
    tokens_used = int(usage.get("input_tokens", 0) or 0) + int(usage.get("output_tokens", 0) or 0)
    return AIResponse(
        text=normalise_latex(reply),
        tokens_used=tokens_used,
        finish_reason=normalize_finish_reason(data.get("stop_reason")),
    )


def _anthropic_stream_lines(response, started):
    buffer = ""
    for chunk in response.iter_text():
        if time.monotonic() - started >= ANTHROPIC_STREAM_WINDOW_SECONDS:
            raise httpx.ReadTimeout("The response exceeded its streaming window.")
        buffer += chunk
        if len(buffer) > 128_000:
            raise ValueError("The provider sent an oversized stream event.")
        lines = buffer.split("\n")
        buffer = lines.pop()
        for line in lines:
            yield line.rstrip("\r")
    if buffer:
        yield buffer.rstrip("\r")


def stream_anthropic_solution(messages: list[dict], api_config: dict, provider: dict, temperature: float, max_tokens: int):
    system_prompt, anthropic_messages = split_anthropic_messages(messages)
    payload = {
        "model": api_config["model"],
        "messages": anthropic_messages,
        "max_tokens": max_tokens,
        "stream": True,
    }
    if provider.get("supports_temperature", True):
        payload["temperature"] = temperature
    if system_prompt:
        payload["system"] = system_prompt

    input_tokens = 0
    output_tokens = 0
    finish_reason = FINISH_REASON_UNKNOWN
    started = time.monotonic()
    with httpx.Client(timeout=ANTHROPIC_STREAM_TIMEOUT) as client:
        with client.stream(
            "POST",
            provider["base_url"],
            headers=get_anthropic_headers(api_config["api_key"]),
            json=payload,
        ) as response:
            response.raise_for_status()
            for line in _anthropic_stream_lines(response, started):
                if not line.startswith("data: "):
                    continue
                raw_data = line.removeprefix("data: ").strip()
                if raw_data == "[DONE]":
                    break
                try:
                    event = json.loads(raw_data)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "error":
                    raise RuntimeError("Anthropic streaming request failed")
                if event.get("type") == "message_start":
                    usage = event.get("message", {}).get("usage", {})
                    try:
                        input_tokens = int(usage.get("input_tokens", 0) or 0)
                    except (AttributeError, TypeError, ValueError):
                        pass
                elif event.get("type") == "message_delta":
                    usage = event.get("usage", {})
                    try:
                        output_tokens = int(usage.get("output_tokens", output_tokens) or 0)
                    except (TypeError, ValueError):
                        pass
                    provider_reason = event.get("delta", {}).get("stop_reason")
                    if provider_reason is not None:
                        finish_reason = normalize_finish_reason(provider_reason)
                if event.get("type") == "content_block_delta":
                    delta = event.get("delta", {})
                    text = delta.get("text", "")
                    if text:
                        yield AIStreamEvent(text=text)
    yield AIStreamEvent(
        done=True,
        tokens_used=input_tokens + output_tokens,
        finish_reason=finish_reason,
    )


def normalise_latex(text: str) -> str:
    """
    Normalise every known LaTeX delimiter variant to the two formats
    that KaTeX on the frontend understands:
      - Display math  →  $$  ...  $$
      - Inline math   →  \\( ... \\)

    Handles:
      \\[ ... \\]                        → $$ ... $$
      [ ... ] (bare, on its own line)    → $$ ... $$
      \\begin{equation}...\\end{equation} → $$ ... $$
      \\begin{equation*}...             → $$ ... $$
      \\begin{align}...\\end{align}      → $$ ... $$
      \\begin{align*}...               → $$ ... $$
      \\begin{aligned}...\\end{aligned}  → $$ ... $$
      $$ ... $$ (already correct)        → kept as-is
      \\( ... \\) (already correct)      → kept as-is
      $ ... $ (single dollar, inline)    → \\( ... \\)
    """
    # 1. \[ ... \] → $$ ... $$
    text = re.sub(
        r'\\\[([\s\S]*?)\\\]',
        lambda m: f'\n$$\n{m.group(1).strip()}\n$$\n',
        text
    )

    # 2. \begin{equation[*]} ... \end{equation[*]} → $$ ... $$
    text = re.sub(
        r'\\begin\{equation\*?\}([\s\S]*?)\\end\{equation\*?\}',
        lambda m: f'\n$$\n{m.group(1).strip()}\n$$\n',
        text
    )

    # 3. \begin{align[*]} ... \end{align[*]} → $$ ... $$
    text = re.sub(
        r'\\begin\{align\*?\}([\s\S]*?)\\end\{align\*?\}',
        lambda m: f'\n$$\n{m.group(1).strip()}\n$$\n',
        text
    )

    # 4. \begin{aligned} ... \end{aligned} → $$ ... $$
    text = re.sub(
        r'\\begin\{aligned\}([\s\S]*?)\\end\{aligned\}',
        lambda m: f'\n$$\n{m.group(1).strip()}\n$$\n',
        text
    )

    # 5. Bare [ ... ] on its own line (the most common AI mistake)
    #    Must not match markdown links like [text](url) or list items like [x]
    text = re.sub(
        r'(?m)^[ \t]*\[([^\[\]\n]+(?:\\.[^\[\]\n]*)*)\][ \t]*$',
        lambda m: f'\n$$\n{m.group(1).strip()}\n$$\n',
        text
    )

    # 6. Collapse any runs of 3+ newlines that the above replacements may create
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text


def get_math_solution(
    conversation_history: list[dict],
    system_prompt: str = MATH_TUTOR_SYSTEM_PROMPT,
    ai_config: dict | None = None,
    max_output_tokens: int = TUTOR_MAX_OUTPUT_TOKENS,
) -> AIResponse:
    """
    Send the conversation to Groq and get a math solution.

    Returns:
        The response text, token usage, and normalized finish reason.
    """
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(conversation_history)

    try:
        api_config, provider = resolve_ai_config(ai_config)
        messages = prepare_provider_messages(messages, api_config["provider"])
        output_limit = get_safe_output_limit(provider, max_output_tokens)
        if provider["client"] == "anthropic":
            return get_anthropic_solution(
                messages,
                api_config,
                provider,
                temperature=0.3,
                max_tokens=output_limit,
            )

        client, model = create_ai_client(ai_config)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            **get_chat_completion_options(provider, temperature=0.3, max_tokens=output_limit),
        )
        tokens_used = response.usage.total_tokens if response.usage else 0
        choice = response.choices[0]
        reply = normalise_latex(choice.message.content or "")
        return AIResponse(
            text=reply,
            tokens_used=tokens_used,
            finish_reason=normalize_finish_reason(getattr(choice, "finish_reason", None)),
        )
    except Exception as error:
        logger.warning("AI provider request failed (%s)", type(error).__name__)
        return AIResponse(
            text=AI_PROVIDER_ERROR_MESSAGE,
            tokens_used=0,
            finish_reason=FINISH_REASON_ERROR,
        )


def get_math_solution_stream(
    messages_for_ai: list[dict],
    system_prompt: str = MATH_TUTOR_SYSTEM_PROMPT,
    ai_config: dict | None = None,
    max_output_tokens: int = TUTOR_MAX_OUTPUT_TOKENS,
):
    """
    Stream the AI response chunk by chunk.

    Yields:
        Text events followed by one completion event with token and finish metadata.
    """
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(messages_for_ai)

    try:
        api_config, provider = resolve_ai_config(ai_config)
        messages = prepare_provider_messages(messages, api_config["provider"])
        output_limit = get_safe_output_limit(provider, max_output_tokens)
        if provider["client"] == "anthropic":
            yield from stream_anthropic_solution(
                messages,
                api_config,
                provider,
                temperature=0.3,
                max_tokens=output_limit,
            )
            return

        client, model = create_ai_client(ai_config)
        stream_options = {}
        if provider.get("supports_stream_usage", False):
            stream_options["stream_options"] = {"include_usage": True}
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            **get_chat_completion_options(provider, temperature=0.3, max_tokens=output_limit),
            **stream_options,
        )
        tokens_used = 0
        finish_reason = FINISH_REASON_UNKNOWN
        for chunk in stream:
            tokens_used = get_stream_usage_total(getattr(chunk, "usage", None)) or tokens_used
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            choice = choices[0]
            provider_reason = getattr(choice, "finish_reason", None)
            if provider_reason is not None:
                finish_reason = normalize_finish_reason(provider_reason)
            delta = getattr(choice, "delta", None)
            content = getattr(delta, "content", "") or ""
            if content:
                yield AIStreamEvent(text=content)

        yield AIStreamEvent(
            done=True,
            tokens_used=tokens_used,
            finish_reason=finish_reason,
        )

    except Exception as error:
        logger.warning("AI provider streaming request failed (%s)", type(error).__name__)
        yield AIStreamEvent(
            text=AI_PROVIDER_ERROR_MESSAGE,
            done=True,
            finish_reason=FINISH_REASON_ERROR,
        )


def extract_equation(user_message: str, ai_config: dict | None = None) -> str | None:
    """
    Use the AI to extract a solvable math equation from a word problem.

    E.g. "I have 12 apples and give away 5" → "12 - 5"
    E.g. "A rectangle is 8 by 3, what's the area?" → "8 * 3"
    E.g. "What is the meaning of life?" → None (not a math problem)

    Returns the equation string, or None if it's not a math problem.
    """
    messages = [
        {
            "role": "system",
            "content": (
                "You are a math equation extractor. The user will give you a message. "
                "If it contains a math problem (word problem, arithmetic, algebra, etc.), "
                "extract ONLY the mathematical equation or expression and output it in "
                "SymPy-compatible Python format.\n\n"
                "Rules:\n"
                "- Output ONLY the equation/expression, nothing else.\n"
                "- Use Python math syntax: * for multiply, ** for power, / for divide.\n"
                "- For equations, use the format: left_side = right_side (with a single =).\n"
                "- Use 'x' as the variable if one is needed.\n"
                "- If it's a simple calculation, just output the expression (e.g. '12 - 5').\n"
                "- If there is NO math problem in the message, output exactly: NONE\n\n"
                "Examples:\n"
                "  'I have 12 apples and give away 5' -> '12 - 5'\n"
                "  'A rectangle is 8 by 3, what is the area?' -> '8 * 3'\n"
                "  'If 3x + 7 = 22, what is x?' -> '3*x + 7 = 22'\n"
                "  'What is 15% of 200?' -> '0.15 * 200'\n"
                "  'A car travels 60 mph for 2.5 hours' -> '60 * 2.5'\n"
                "  'What is algebra?' -> 'NONE'\n"
                "  'Hello how are you?' -> 'NONE'\n"
            ),
        },
        {"role": "user", "content": user_message},
    ]

    try:
        api_config, provider = resolve_ai_config(ai_config)
        if provider["client"] == "anthropic":
            response = get_anthropic_solution(
                messages,
                api_config,
                provider,
                temperature=0.0,
                max_tokens=EXTRACTION_MAX_OUTPUT_TOKENS,
            )
            result = response.text.strip()
        else:
            client, model = create_ai_client(ai_config)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                **get_chat_completion_options(
                    provider,
                    temperature=0.0,
                    max_tokens=EXTRACTION_MAX_OUTPUT_TOKENS,
                ),
            )
            result = response.choices[0].message.content.strip()

        # If the AI says it's not a math problem, return None
        if result.upper() == "NONE" or not result:
            return None

        # Clean up — remove backticks, quotes, or "Answer:" prefixes
        result = result.strip("`\"' ")
        result = result.removeprefix("```python").removeprefix("```").removesuffix("```")
        result = result.strip()

        return result if result and result.upper() != "NONE" else None
    except Exception:
        return None
