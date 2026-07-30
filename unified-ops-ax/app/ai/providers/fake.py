"""Offline deterministic provider. Lets the whole platform (and tests) run
without any API key. Echoes grounding context so RAG answers are verifiable."""
from __future__ import annotations

from app.ai.providers.base import ChatMessage


class FakeProvider:
    name = "fake"

    def complete(self, messages: list[ChatMessage], *, model: str | None = None, **kwargs) -> str:
        user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        grounded = "[grounded] " if "CONTEXT:" in system or "CONTEXT:" in user else ""
        return f"{grounded}(fake-llm) answer to: {user[:280]}"
