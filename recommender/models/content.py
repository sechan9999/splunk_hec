"""Content-based: item feature vectors vs. interaction-weighted user profile."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import BaseRecommender, Context


def item_features(items: pd.DataFrame) -> np.ndarray:
    cats = sorted(items["category"].unique())
    n = int(items["item_id"].max()) + 1
    feats = np.zeros((n, len(cats) + 1))
    idx = items["item_id"].to_numpy()
    for c_i, cat in enumerate(cats):
        feats[idx[items["category"].to_numpy() == cat], c_i] = 1.0
    feats[idx, -1] = items["price_tier"].to_numpy() / 3.0
    return feats


class ContentBasedRecommender(BaseRecommender):
    name = "content"

    def __init__(self) -> None:
        super().__init__()
        self.feats: np.ndarray | None = None
        self.profiles: dict[int, np.ndarray] = {}

    def _fit(self, events: pd.DataFrame, items: pd.DataFrame) -> None:
        self.feats = item_features(items)
        fnorm = self.feats / (np.linalg.norm(self.feats, axis=1, keepdims=True) + 1e-12)
        self._fnorm = fnorm
        for u, grp in events.groupby("user_id"):
            w = grp["weight"].to_numpy()
            prof = (fnorm[grp["item_id"].to_numpy()] * w[:, None]).sum(axis=0)
            n = np.linalg.norm(prof)
            self.profiles[int(u)] = prof / n if n > 0 else prof

    def score(self, user_id: int, context: Context | None = None) -> np.ndarray:
        prof = self.profiles.get(user_id)
        if prof is None:
            return np.zeros(self.n_items)
        return self._fnorm @ prof
