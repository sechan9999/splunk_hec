"""AI Gateway — one interface, many LLMs. Routes to the configured provider
and lets callers override per request. Central choke point for future
policy: rate limits, cost routing, PII redaction, audit logging."""
from __future__ import annotations

from functools import lru_cache

from app.ai.providers.base import ChatMessage, LLMProvider
from app.config import get_settings


def _build(provider: str) -> LLMProvider:
    if provider == "fake":
        from app.ai.providers.fake import FakeProvider

        return FakeProvider()
    if provider == "anthropic":
        from app.ai.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    if provider == "openai":
        from app.ai.providers.openai_provider import OpenAIProvider

        return OpenAIProvider()
    if provider == "onprem":
        from app.ai.providers.onprem_provider import OnPremProvider

        return OnPremProvider()
    raise ValueError(f"unknown LLM provider: {provider}")


@lru_cache
def _provider_cache(provider: str) -> LLMProvider:
    return _build(provider)


class AIGateway:
    def __init__(self, default_provider: str | None = None) -> None:
        self._default = default_provider or get_settings().default_llm_provider

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        provider: str | None = None,
        model: str | None = None,
        **kwargs,
    ) -> dict:
        name = provider or self._default
        impl = _provider_cache(name)
        text = impl.complete(messages, model=model, **kwargs)
        return {"provider": name, "model": model, "content": text}


def get_gateway() -> AIGateway:
    return AIGateway()
