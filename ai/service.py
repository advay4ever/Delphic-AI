"""
Delphic AI - AI Service
"""

import re
import json
import httpx
from openai import OpenAI
from ai.prompt import (
    ANTHROPIC_API_KEY,
    DEEPSEEK_API_KEY,
    GOOGLE_API_KEY,
    GROQ_API_KEY,
    MISTRAL_API_KEY,
    OPENAI_API_KEY,
    TOGETHER_API_KEY,
    XAI_API_KEY,
    MATH_TUTOR_SYSTEM_PROMPT,
)


SUPPORTED_AI_PROVIDERS = {
    "groq": {
        "label": "Groq",
        "client": "openai_compatible",
        "base_url": "https://api.groq.com/openai/v1",
        "model": "openai/gpt-oss-120b",
        "env_key": GROQ_API_KEY,
    },
    "openai": {
        "label": "OpenAI",
        "client": "openai_compatible",
        "base_url": None,
        "model": "gpt-5-mini",
        "token_limit_parameter": "max_completion_tokens",
        "supports_temperature": False,
        "env_key": OPENAI_API_KEY,
    },
    "anthropic": {
        "label": "Anthropic",
        "client": "anthropic",
        "base_url": "https://api.anthropic.com/v1/messages",
        "model": "claude-haiku-4-5-20251001",
        "env_key": ANTHROPIC_API_KEY,
    },
    "google": {
        "label": "Google Gemini",
        "client": "openai_compatible",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-3.5-flash",
        "env_key": GOOGLE_API_KEY,
    },
    "mistral": {
        "label": "Mistral",
        "client": "openai_compatible",
        "base_url": "https://api.mistral.ai/v1",
        "model": "magistral-small-latest",
        "env_key": MISTRAL_API_KEY,
    },
    "together": {
        "label": "Together AI",
        "client": "openai_compatible",
        "base_url": "https://api.together.ai/v1",
        "model": "openai/gpt-oss-120b",
        "env_key": TOGETHER_API_KEY,
    },
    "xai": {
        "label": "xAI",
        "client": "openai_compatible",
        "base_url": "https://api.x.ai/v1",
        "model": "grok-4.20-0309-reasoning",
        "env_key": XAI_API_KEY,
    },
    "deepseek": {
        "label": "DeepSeek",
        "client": "openai_compatible",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-pro",
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
    }
    if len(clean_key) < 12 or clean_key in placeholders or clean_key.startswith("your-"):
        return "Paste a full API key."
    return None


def looks_like_real_api_key(api_key: str | None) -> bool:
    return get_api_key_validation_error(api_key) is None


def get_public_provider_options() -> list[dict]:
    """Return provider options without exposing API keys."""
    return [
        {"id": provider_id, "label": config["label"], "model": config["model"]}
        for provider_id, config in SUPPORTED_AI_PROVIDERS.items()
    ]


def get_default_provider_config() -> dict | None:
    """Use environment keys as a fallback for local development."""
    for provider_id in SUPPORTED_AI_PROVIDERS:
        config = SUPPORTED_AI_PROVIDERS[provider_id]
        if looks_like_real_api_key(config["env_key"]):
            return {"provider": provider_id, "api_key": config["env_key"], "source": "env"}
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
    return {**config, "api_key": api_key}, provider


def create_ai_client(ai_config: dict | None = None) -> tuple[OpenAI, str]:
    config, provider = resolve_ai_config(ai_config)
    kwargs = {"api_key": config["api_key"]}
    if provider["base_url"]:
        kwargs["base_url"] = provider["base_url"]
    return OpenAI(**kwargs), provider["model"]


def get_chat_completion_options(provider: dict, temperature: float, max_tokens: int) -> dict:
    """Build provider-specific Chat Completions options."""
    token_limit_parameter = provider.get("token_limit_parameter", "max_tokens")
    options = {token_limit_parameter: max_tokens}
    if provider.get("supports_temperature", True):
        options["temperature"] = temperature
    return options


def split_anthropic_messages(messages: list[dict]) -> tuple[str, list[dict]]:
    system_parts = []
    anthropic_messages = []
    for message in messages:
        role = message.get("role")
        content = str(message.get("content", ""))
        if role == "system":
            system_parts.append(content)
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


def get_anthropic_solution(messages: list[dict], api_config: dict, provider: dict, temperature: float, max_tokens: int) -> tuple[str, int]:
    system_prompt, anthropic_messages = split_anthropic_messages(messages)
    payload = {
        "model": provider["model"],
        "messages": anthropic_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
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
    return normalise_latex(reply), tokens_used


def stream_anthropic_solution(messages: list[dict], api_config: dict, provider: dict, temperature: float, max_tokens: int):
    system_prompt, anthropic_messages = split_anthropic_messages(messages)
    payload = {
        "model": provider["model"],
        "messages": anthropic_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    if system_prompt:
        payload["system"] = system_prompt

    with httpx.Client(timeout=None) as client:
        with client.stream(
            "POST",
            provider["base_url"],
            headers=get_anthropic_headers(api_config["api_key"]),
            json=payload,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.startswith("data: "):
                    continue
                raw_data = line.removeprefix("data: ").strip()
                if raw_data == "[DONE]":
                    break
                try:
                    event = json.loads(raw_data)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "content_block_delta":
                    delta = event.get("delta", {})
                    text = delta.get("text", "")
                    if text:
                        yield text, False, 0
    yield "", True, 0


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
) -> tuple[str, int]:
    """
    Send the conversation to Groq and get a math solution.

    Returns:
        A tuple of (reply_text, tokens_used)
    """
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(conversation_history)

    try:
        api_config, provider = resolve_ai_config(ai_config)
        if provider["client"] == "anthropic":
            return get_anthropic_solution(messages, api_config, provider, temperature=0.3, max_tokens=2048)

        client, model = create_ai_client(ai_config)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            **get_chat_completion_options(provider, temperature=0.3, max_tokens=2048),
        )
        tokens_used = response.usage.total_tokens if response.usage else 0
        reply = normalise_latex(response.choices[0].message.content)
        return reply, tokens_used
    except Exception as e:
        return f"⚠️ Sorry, I encountered an error: {str(e)}", 0


def get_math_solution_stream(
    messages_for_ai: list[dict],
    system_prompt: str = MATH_TUTOR_SYSTEM_PROMPT,
    ai_config: dict | None = None,
):
    """
    Stream the AI response chunk by chunk.

    Yields:
        (chunk_text, is_done, total_tokens)
        - chunk_text: a piece of the reply (str)
        - is_done: True only on the final yield
        - total_tokens: only set on the final yield, 0 otherwise
    """
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(messages_for_ai)

    try:
        api_config, provider = resolve_ai_config(ai_config)
        if provider["client"] == "anthropic":
            yield from stream_anthropic_solution(messages, api_config, provider, temperature=0.3, max_tokens=2048)
            return

        client, model = create_ai_client(ai_config)
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            **get_chat_completion_options(provider, temperature=0.3, max_tokens=2048),
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            content = delta.content or ""
            if content:
                yield content, False, 0

        # Send a final done signal — Groq streaming doesn't give usage in stream mode
        yield "", True, 0

    except Exception as e:
        yield f"⚠️ Sorry, I encountered an error: {str(e)}", True, 0


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
            result, _ = get_anthropic_solution(messages, api_config, provider, temperature=0.0, max_tokens=100)
            result = result.strip()
        else:
            client, model = create_ai_client(ai_config)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                **get_chat_completion_options(provider, temperature=0.0, max_tokens=100),
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
