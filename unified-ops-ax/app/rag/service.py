"""RAG query orchestration: embed query -> security-trimmed retrieve ->
ground the AI Gateway -> return answer with citations."""
from __future__ import annotations

from app.ai.embeddings import get_embedder
from app.ai.gateway import get_gateway
from app.rag.vectorstore import get_vector_store
from app.security.rbac import principals_for

_SYSTEM = (
    "You answer strictly from the provided CONTEXT about internal company "
    "documents. If the context is insufficient, say so. Cite sources by title."
)


def retrieve(query: str, principals: set[str] | list[str], k: int = 5):
    vec = get_embedder().embed([query])[0]
    return get_vector_store().search(vec, k=k, principals=principals)


def answer(query: str, *, role: str, employee_id: str | None = None, k: int = 5) -> dict:
    principals = principals_for(role, employee_id)
    hits = retrieve(query, principals, k=k)
    context = "\n\n".join(f"[{h.meta.get('title', 'doc')}] {h.text}" for h in hits)
    messages = [
        {"role": "system", "content": f"{_SYSTEM}\n\nCONTEXT:\n{context or '(none)'}"},
        {"role": "user", "content": query},
    ]
    result = get_gateway().chat(messages)
    return {
        "answer": result["content"],
        "provider": result["provider"],
        "citations": [{"document_id": h.document_id, "title": h.meta.get("title"), "score": round(h.score, 4)} for h in hits],
        "trimmed": True,
    }
