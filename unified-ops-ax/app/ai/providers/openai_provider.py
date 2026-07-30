from __future__ import annotations

from app.ai.providers.base import ChatMessage
from app.config import get_settings


class OpenAIProvider:
    """Works for OpenAI and any OpenAI-compatible endpoint (used by onprem)."""
    name = "openai"

    def __init__(self, base_url: str | None = None, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self._base_url = base_url
        self._api_key = api_key or settings.openai_api_key
        self._model = model or settings.openai_model
        self._client = None

    def _lazy_client(self):
        if self._client is None:
            from openai import OpenAI  # lazy import — optional dependency

            self._client = OpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client

    def complete(self, messages: list[ChatMessage], *, model: str | None = None, **kwargs) -> str:
        client = self._lazy_client()
        resp = client.chat.completions.create(
            model=model or self._model,
            messages=[{"role": m["role"], "content": m["content"]} for m in messages],
            max_tokens=kwargs.get("max_tokens", 1024),
        )
        return resp.choices[0].message.content or ""
