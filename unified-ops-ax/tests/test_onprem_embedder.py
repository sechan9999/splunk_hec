"""Keyless onprem embedder (Ollama/LocalAI) — offline via httpx.MockTransport."""
import httpx
import numpy as np

from app.ai.embeddings import OnPremEmbedder


def _embedder(handler):
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return OnPremEmbedder(base_url="http://localhost:11434", model="nomic-embed-text", http=http)


def test_openai_compatible_endpoint():
    def handler(request):
        assert request.url.path == "/v1/embeddings"
        return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2, 0.3]},
                                                  {"embedding": [0.4, 0.5, 0.6]}]})
    vecs = _embedder(handler).embed(["a", "b"])
    assert vecs.shape == (2, 3)
    assert np.allclose(vecs[0], [0.1, 0.2, 0.3])


def test_falls_back_to_ollama_native_batch():
    def handler(request):
        if request.url.path == "/v1/embeddings":
            return httpx.Response(404, json={})           # OpenAI-compat unavailable
        assert request.url.path == "/api/embed"
        return httpx.Response(200, json={"embeddings": [[1.0, 0.0], [0.0, 1.0]]})
    vecs = _embedder(handler).embed(["x", "y"])
    assert vecs.shape == (2, 2)


def test_falls_back_to_single_embeddings_endpoint():
    calls = {"single": 0}

    def handler(request):
        if request.url.path in ("/v1/embeddings", "/api/embed"):
            return httpx.Response(404, json={})
        assert request.url.path == "/api/embeddings"
        calls["single"] += 1
        return httpx.Response(200, json={"embedding": [0.5, 0.5]})
    vecs = _embedder(handler).embed(["one", "two"])
    assert vecs.shape == (2, 2)
    assert calls["single"] == 2  # looped per text


def test_get_embedder_routes_to_onprem(monkeypatch):
    from app.ai import embeddings as emb
    monkeypatch.setenv("EMBEDDING_PROVIDER", "onprem")
    emb.get_settings.cache_clear()
    try:
        assert emb.get_embedder().provider == "onprem"
    finally:
        emb.get_settings.cache_clear()
