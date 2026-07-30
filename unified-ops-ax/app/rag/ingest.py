"""Ingest a document: persist -> chunk -> embed -> index (with ACL snapshot)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.embeddings import get_embedder
from app.domain.models import Document, DocumentChunk
from app.rag.vectorstore import VectorRecord, get_vector_store


def chunk_text(text: str, size: int = 800, overlap: int = 100) -> list[str]:
    text = text.strip()
    if not text:
        return []
    chunks, start = [], 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def ingest_document(
    session: Session,
    *,
    title: str,
    content: str,
    acl: list[str] | None = None,
    source: str = "local",
    external_id: str | None = None,
    uri: str | None = None,
    meta: dict | None = None,
) -> Document:
    acl = acl or []
    doc = Document(
        title=title, source=source, external_id=external_id, uri=uri, acl=acl, meta=meta or {}
    )
    session.add(doc)
    session.flush()

    pieces = chunk_text(content)
    embedder = get_embedder()
    vectors = embedder.embed(pieces) if pieces else []
    store = get_vector_store()

    records: list[VectorRecord] = []
    for i, piece in enumerate(pieces):
        chunk = DocumentChunk(document_id=doc.id, ordinal=i, text=piece, acl=acl)
        session.add(chunk)
        session.flush()
        records.append(
            VectorRecord(
                id=chunk.id,
                vector=vectors[i],
                text=piece,
                document_id=doc.id,
                acl=acl,
                meta={"title": title, "ordinal": i},
            )
        )
    if records:
        store.add(records)
    return doc
