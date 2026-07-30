"""Connector port (adapter pattern) — the seam that keeps SaaS out of the
core. Each source maps its native permissions to `acl` principals so the
platform's security trimming stays source-faithful."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class SourceDocument:
    external_id: str
    title: str
    content: str
    acl: list[str] = field(default_factory=list)  # principals mirrored from source
    uri: str | None = None
    meta: dict = field(default_factory=dict)


class ConnectorPort(Protocol):
    source: str

    def list_documents(self) -> list[SourceDocument]:
        ...
