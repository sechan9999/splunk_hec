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


def get_embedder():
    settings = get_settings()
    if settings.embedding_provider == "openai":
        return OpenAIEmbedder()
    return FakeEmbedder(dim=settings.embedding_dim)
