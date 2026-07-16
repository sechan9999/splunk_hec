"""Item-item collaborative filtering on implicit-weighted interactions.

Interactions are BM25-reweighted before computing similarity: rare items
get an IDF boost and heavy users are length-normalized, so similarities
aren't dominated by popular items / hyperactive users.

sim(i,j) = cosine with shrinkage: dot(i,j) / (||i||·||j|| + beta)
score(u,i) = sum_j sim(i,j) * bm25_weight(u,j)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import BaseRecommender, Context


class ItemItemCFRecommender(BaseRecommender):
    name = "item_cf"

    def __init__(self, shrinkage: float = 25.0, recency_decay: float = 0.02,
                 top_n_sim: int = 50, bm25_k1: float = 1.2, bm25_b: float = 0.75) -> None:
        super().__init__()
        self.shrinkage = shrinkage
        self.recency_decay = recency_decay
        self.top_n_sim = top_n_sim
        self.bm25_k1 = bm25_k1
        self.bm25_b = bm25_b
        self.sim: np.ndarray | None = None
        self.user_vec: dict[int, np.ndarray] = {}

    def _bm25(self, R: np.ndarray) -> np.ndarray:
        n_users = R.shape[0]
        df = (R > 0).sum(axis=0)
        idf = np.log((n_users - df + 0.5) / (df + 0.5) + 1)
        ulen = R.sum(axis=1)
        avg = ulen[ulen > 0].mean()
        denom = self.bm25_k1 * (1 - self.bm25_b + self.bm25_b * (ulen / avg))[:, None] + R
        return idf[None, :] * R * (self.bm25_k1 + 1) / np.where(denom == 0, 1, denom)

    def _fit(self, events: pd.DataFrame, items: pd.DataFrame) -> None:
        n_users = int(events["user_id"].max()) + 1
        max_day = events["day"].max()
        rec = np.exp(-self.recency_decay * (max_day - events["day"].to_numpy()))
        w = events["weight"].to_numpy() * rec

        # dense user-item matrix (small scale; sparse for production)
        R = np.zeros((n_users, self.n_items))
        np.add.at(R, (events["user_id"].to_numpy(), events["item_id"].to_numpy()), w)
        R = self._bm25(R)

        norms = np.linalg.norm(R, axis=0)
        sim = (R.T @ R) / (np.outer(norms, norms) + self.shrinkage)
        np.fill_diagonal(sim, 0.0)

        # keep only top-N neighbors per item (noise reduction + speed)
        if self.top_n_sim < self.n_items:
            thresh = np.partition(sim, -self.top_n_sim, axis=1)[:, -self.top_n_sim][:, None]
            sim[sim < thresh] = 0.0
        self.sim = sim
        self.user_vec = {u: R[u] for u in np.unique(events["user_id"].to_numpy())}

    def score(self, user_id: int, context: Context | None = None) -> np.ndarray:
        vec = self.user_vec.get(user_id)
        if vec is None:
            return np.zeros(self.n_items)
        return self.sim @ vec
