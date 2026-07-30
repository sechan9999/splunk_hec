from __future__ import annotations

from typing import Protocol, TypedDict


class ChatMessage(TypedDict):
    role: str  # system | user | assistant
    content: str


class LLMProvider(Protocol):
    name: str

    def complete(self, messages: list[ChatMessage], *, model: str | None = None, **kwargs) -> str:
        ...
