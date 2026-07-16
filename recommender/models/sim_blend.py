"""Similarity-level CF + content blending (vs score-level in hybrid).

sim_blend(i,j) = alpha * sim_cf(i,j) + (1 - alpha) * sim_content(i,j)
score(u,i)     = sim_blend @ user_vec

Blending at the similarity matrix lets content fill in neighbors for
items with thin interaction data *before* scoring — a cold-item fix that
score-level fusion can't express.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import BaseRecommender, Context
from .content import item_features
from .item_cf import ItemItemCFRecommender


class SimBlendRecommender(BaseRecommender):
    name = "sim_blend"

    def __init__(self, alpha: float = 0.7, top_n_sim: int = 50, **cf_kwargs) -> None:
        super().__init__()
        self.alpha = alpha
        self.top_n_sim = top_n_sim
        self.cf = ItemItemCFRecommender(top_n_sim=top_n_sim, **cf_kwargs)
        self.sim: np.ndarray | None = None

    def _content_sim(self, items: pd.DataFrame) -> np.ndarray:
        feats = item_features(items)
        norm = feats / (np.linalg.norm(feats, axis=1, keepdims=True) + 1e-12)
        sim = norm @ norm.T
        np.fill_diagonal(sim, 0.0)
        return sim

    def set_alpha(self, alpha: float) -> None:
        self.alpha = alpha
        self._blend()

    def _blend(self) -> None:
        # each matrix scaled to unit max so alpha weighs comparable ranges
        cf_s = self._cf_sim / (self._cf_sim.max() + 1e-12)
        ct_s = self._ct_sim / (self._ct_sim.max() + 1e-12)
        sim = self.alpha * cf_s + (1 - self.alpha) * ct_s
        if self.top_n_sim < self.n_items:
            thresh = np.partition(sim, -self.top_n_sim, axis=1)[:, -self.top_n_sim][:, None]
            sim[sim < thresh] = 0.0
        self.sim = sim

    def _fit(self, events: pd.DataFrame, items: pd.DataFrame) -> None:
        self.cf.fit(events, items)
        self._cf_sim = self.cf.sim
        self._ct_sim = self._content_sim(items)
        self._blend()

    def score(self, user_id: int, context: Context | None = None) -> np.ndarray:
        vec = self.cf.user_vec.get(user_id)
        if vec is None:
            return np.zeros(self.n_items)
        return self.sim @ vec


def tune_alpha(model: SimBlendRecommender, evaluate_fn, truth_val, ctx_val,
               grid=(0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0), k: int = 10) -> float:
    """Pick alpha on validation NDCG@K (re-blends cached sims, no refit)."""
    best, best_a = -1.0, model.alpha
    for a in grid:
        model.set_alpha(a)
        score = evaluate_fn(model, truth_val, ctx_val, k=k)[f"ndcg@{k}"]
        if score > best:
            best, best_a = score, a
    model.set_alpha(best_a)
    return best_a
