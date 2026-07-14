"""Item-item collaborative filtering on implicit-weighted interactions.

sim(i,j) = cosine with shrinkage: dot(i,j) / (||i||·||j|| + beta)
score(u,i) = sum_j sim(i,j) * weight(u,j) * recency(u,j)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import BaseRecommender, Context


class ItemItemCFRecommender(BaseRecommender):
    name = "item_cf"

    def __init__(self, shrinkage: float = 25.0, recency_decay: float = 0.02, top_n_sim: int = 50) -> None:
        super().__init__()
        self.shrinkage = shrinkage
        self.recency_decay = recency_decay
        self.top_n_sim = top_n_sim
        self.sim: np.ndarray | None = None
        self.user_vec: dict[int, np.ndarray] = {}

    def _fit(self, events: pd.DataFrame, items: pd.DataFrame) -> None:
        n_users = int(events["user_id"].max()) + 1
        max_day = events["day"].max()
        rec = np.exp(-self.recency_decay * (max_day - events["day"].to_numpy()))
        w = events["weight"].to_numpy() * rec

        # dense user-item matrix (small scale; sparse for production)
        R = np.zeros((n_users, self.n_items))
        np.add.at(R, (events["user_id"].to_numpy(), events["item_id"].to_numpy()), w)

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
