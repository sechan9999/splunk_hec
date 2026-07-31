"""Embeddings with an offline default. The `fake` provider is a hashing
vectorizer (bag-of-words hashed into fixed dims) so cosine similarity
reflects token overlap — real ranking behavior with no API key."""
from __future__ import annotations

import hashlib
import re

import numpy as np

from app.config import get_settings

_TOKEN = re.compile(r"[a-z0-9가-힣]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class FakeEmbedder:
    provider = "fake"

    def __init__(self, dim: int) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            for tok in _tokens(text):
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                out[i, h % self.dim] += 1.0
            norm = np.linalg.norm(out[i])
            if norm:
                out[i] /= norm
        return out


class OpenAIEmbedder:
    provider = "openai"

    def __init__(self, model: str = "text-embedding-3-small") -> None:
        self.model = model
        self._client = None

    def embed(self, texts: list[str]) -> np.ndarray:
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=get_settings().openai_api_key)
        resp = self._client.embeddings.create(model=self.model, input=texts)
        return np.array([d.embedding for d in resp.data], dtype=np.float32)


class OnPremEmbedder:
    """Keyless local embeddings (Ollama / LocalAI). No API key. Tries the
    OpenAI-compatible /v1/embeddings first, then Ollama-native /api/embed
    (batch), then /api/embeddings (single). httpx client injectable for tests."""
    provider = "onprem"

    def __init__(self, base_url: str | None = None, model: str | None = None, http=None) -> None:
        import httpx

        settings = get_settings()
        self._base = (base_url or settings.onprem_base_url).rstrip("/")
        self._model = model or getattr(settings, "onprem_embedding_model", "nomic-embed-text")
        self._http = http or httpx.Client(timeout=60.0)

    def embed(self, texts: list[str]) -> np.ndarray:
        # 1) OpenAI-compatible endpoint
        v1 = f"{self._base}/v1/embeddings" if not self._base.endswith("/v1") else f"{self._base}/embeddings"
        try:
            resp = self._http.post(v1, json={"model": self._model, "input": texts})
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                if data:
                    return np.array([d["embedding"] for d in data], dtype=np.float32)
        except Exception:
            pass
        # 2) Ollama-native batch endpoint
        try:
            resp = self._http.post(f"{self._base}/api/embed", json={"model": self._model, "input": texts})
            if resp.status_code == 200:
                embs = resp.json().get("embeddings")
                if embs:
                    return np.array(embs, dtype=np.float32)
        except Exception:
            pass
        # 3) Ollama-native single endpoint (loop)
        out = []
        for text in texts:
            resp = self._http.post(f"{self._base}/api/embeddings", json={"model": self._model, "prompt": text})
            resp.raise_for_status()
            out.append(resp.json()["embedding"])
        return np.array(out, dtype=np.float32)


def get_embedder():
    settings = get_settings()
    if settings.embedding_provider == "openai":
        return OpenAIEmbedder()
    if settings.embedding_provider == "onprem":
        return OnPremEmbedder()
    return FakeEmbedder(dim=settings.embedding_dim)
