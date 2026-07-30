"""On-prem provider via an OpenAI-compatible endpoint (Ollama / vLLM / TGI).
This is the extension path to fully on-prem AI — no code change elsewhere,
just point ONPREM_BASE_URL at the internal endpoint."""
from __future__ import annotations

from app.ai.providers.base import ChatMessage
from app.ai.providers.openai_provider import OpenAIProvider
from app.config import get_settings


class OnPremProvider:
    name = "onprem"

    def __init__(self) -> None:
        settings = get_settings()
        base = settings.onprem_base_url.rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        self._delegate = OpenAIProvider(base_url=base, api_key="not-needed", model=settings.onprem_model)

    def complete(self, messages: list[ChatMessage], *, model: str | None = None, **kwargs) -> str:
        return self._delegate.complete(messages, model=model, **kwargs)
