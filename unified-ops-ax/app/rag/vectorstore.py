"""Pluggable vector store. `memory` runs anywhere (dev/test). `pgvector`
is the prod backend (single Postgres alongside the hub). Security trimming
is applied inside search() BEFORE top-k, so trimmed docs can never surface."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.config import get_settings
from app.security.acl import can_access


@dataclass
class VectorRecord:
    id: str
    vector: np.ndarray
    text: str
    document_id: str
    acl: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)


@dataclass
class SearchHit:
    chunk_id: str
    document_id: str
    text: str
    score: float
    meta: dict


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._records: list[VectorRecord] = []

    def add(self, records: list[VectorRecord]) -> None:
        self._records.extend(records)

    def clear(self) -> None:
        self._records.clear()

    def search(self, query: np.ndarray, k: int, principals: set[str] | list[str]) -> list[SearchHit]:
        q = query / (np.linalg.norm(query) or 1.0)
        principals = set(principals)
        hits: list[SearchHit] = []
        for rec in self._records:
            if not can_access(rec.acl, principals):  # security trimming
                continue
            score = float(np.dot(rec.vector, q))
            hits.append(SearchHit(rec.id, rec.document_id, rec.text, score, rec.meta))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]


class PgVectorStore:
    """Prod backend. Requires `pgvector` extension + `document_chunks.embedding`
    column. Security trimming is pushed into SQL:

        SELECT id, document_id, text, 1 - (embedding <=> :q) AS score
        FROM document_chunks
        WHERE acl = '[]'::jsonb OR acl ?| :principals    -- trim
        ORDER BY embedding <=> :q
        LIMIT :k;
    """

    def __init__(self) -> None:
        raise NotImplementedError(
            "pgvector backend is a documented stub. Install pgvector, add an "
            "embedding column, and implement add()/search() with the SQL above."
        )


def get_vector_store():
    if get_settings().vector_backend == "pgvector":
        return PgVectorStore()
    return _MEMORY_SINGLETON


_MEMORY_SINGLETON = InMemoryVectorStore()
