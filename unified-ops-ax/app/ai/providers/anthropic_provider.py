from __future__ import annotations

from app.ai.providers.base import ChatMessage
from app.config import get_settings


class AnthropicProvider:
    name = "anthropic"

    def __init__(self) -> None:
        self._settings = get_settings()
        self._client = None

    def _lazy_client(self):
        if self._client is None:
            import anthropic  # lazy import — optional dependency

            self._client = anthropic.Anthropic(api_key=self._settings.anthropic_api_key)
        return self._client

    def complete(self, messages: list[ChatMessage], *, model: str | None = None, **kwargs) -> str:
        client = self._lazy_client()
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        convo = [m for m in messages if m["role"] != "system"]
        resp = client.messages.create(
            model=model or self._settings.anthropic_model,
            max_tokens=kwargs.get("max_tokens", 1024),
            system=system or None,
            messages=[{"role": m["role"], "content": m["content"]} for m in convo],
        )
        return "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")
