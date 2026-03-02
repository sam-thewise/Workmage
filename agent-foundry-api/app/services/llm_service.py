"""LLM completion service via LiteLLM."""
from typing import Any

from app.core.config import settings

# Map provider prefix to env var for platform key
PROVIDER_ENV_MAP = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "ollama": None,  # no key needed for local
}


def _get_api_key(provider: str, user_key: str | None) -> str | None:
    """Resolve API key: user's BYOK or platform key."""
    if user_key:
        return user_key
    env_var = PROVIDER_ENV_MAP.get(provider)
    if env_var:
        return getattr(settings, env_var, None) or ""
    return None


def completion(
    model: str,
    messages: list[dict[str, str]],
    api_key: str | None = None,
    stream: bool = False,
) -> Any:
    """Run completion via LiteLLM. Model format: openai/gpt-5.2, openai/gpt-5-mini, anthropic/claude-3, etc."""
    import litellm

    provider = model.split("/")[0] if "/" in model else "openai"
    key = _get_api_key(provider, api_key)
    kwargs: dict[str, Any] = {"model": model, "messages": messages, "stream": stream}
    if key and provider != "ollama":
        kwargs["api_key"] = key
    return litellm.completion(**kwargs)


async def acompletion(
    model: str,
    messages: list[dict[str, str]],
    api_key: str | None = None,
    stream: bool = False,
) -> Any:
    """Async completion via LiteLLM."""
    import litellm

    provider = model.split("/")[0] if "/" in model else "openai"
    key = _get_api_key(provider, api_key)
    kwargs: dict[str, Any] = {"model": model, "messages": messages, "stream": stream}
    if key and provider != "ollama":
        kwargs["api_key"] = key
    return await litellm.acompletion(**kwargs)
