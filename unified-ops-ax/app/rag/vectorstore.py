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
    """Prod backend on Postgres + pgvector. Manages its own `rag_vectors`
    table (self-contained, no ORM change). Security trimming is pushed into
    SQL — public rows (empty acl) or rows whose acl overlaps the caller's
    principals. Requires: `pip install pgvector psycopg2-binary` and a
    Postgres DATABASE_URL. Verified against live Postgres only."""

    def __init__(self) -> None:
        from sqlalchemy import text

        from app.db import engine

        self._engine = engine
        self._dim = get_settings().embedding_dim
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(text(
                f"CREATE TABLE IF NOT EXISTS rag_vectors ("
                f"id text PRIMARY KEY, document_id text, text text, "
                f"acl jsonb DEFAULT '[]'::jsonb, meta jsonb DEFAULT '{{}}'::jsonb, "
                f"embedding vector({self._dim}))"
            ))

    @staticmethod
    def _vec(v: np.ndarray) -> str:
        return "[" + ",".join(f"{x:.6f}" for x in v.tolist()) + "]"

    def add(self, records: list[VectorRecord]) -> None:
        from sqlalchemy import text

        import json as _json
        with self._engine.begin() as conn:
            for r in records:
                conn.execute(
                    text("INSERT INTO rag_vectors (id, document_id, text, acl, meta, embedding) "
                         "VALUES (:id, :doc, :txt, CAST(:acl AS jsonb), CAST(:meta AS jsonb), CAST(:emb AS vector)) "
                         "ON CONFLICT (id) DO UPDATE SET embedding = EXCLUDED.embedding, acl = EXCLUDED.acl"),
                    {"id": r.id, "doc": r.document_id, "txt": r.text,
                     "acl": _json.dumps(r.acl), "meta": _json.dumps(r.meta), "emb": self._vec(r.vector)},
                )

    def clear(self) -> None:
        from sqlalchemy import text

        with self._engine.begin() as conn:
            conn.execute(text("TRUNCATE rag_vectors"))

    def search(self, query: np.ndarray, k: int, principals: set[str] | list[str]) -> list[SearchHit]:
        from sqlalchemy import text

        with self._engine.connect() as conn:
            rows = conn.execute(
                text("SELECT id, document_id, text, meta, 1 - (embedding <=> CAST(:q AS vector)) AS score "
                     "FROM rag_vectors "
                     "WHERE jsonb_array_length(acl) = 0 OR acl ?| :principals "  # security trimming
                     "ORDER BY embedding <=> CAST(:q AS vector) LIMIT :k"),
                {"q": self._vec(query), "principals": list(principals), "k": k},
            ).mappings().all()
        return [SearchHit(r["id"], r["document_id"], r["text"], float(r["score"]), r["meta"] or {}) for r in rows]


def get_vector_store():
    if get_settings().vector_backend == "pgvector":
        return PgVectorStore()
    return _MEMORY_SINGLETON


_MEMORY_SINGLETON = InMemoryVectorStore()
