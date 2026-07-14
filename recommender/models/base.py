"""Common recommender interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Context:
    device: str = "mobile"
    hour_bucket: str = "evening"
    is_weekend: bool = False


def minmax(scores: np.ndarray) -> np.ndarray:
    lo, hi = scores.min(), scores.max()
    if hi - lo < 1e-12:
        return np.zeros_like(scores)
    return (scores - lo) / (hi - lo)


class BaseRecommender(ABC):
    name: str = "base"

    def __init__(self) -> None:
        self.n_items: int = 0
        self.seen: dict[int, set[int]] = {}

    def fit(self, events: pd.DataFrame, items: pd.DataFrame) -> "BaseRecommender":
        self.n_items = int(items["item_id"].max()) + 1
        self.seen = events.groupby("user_id")["item_id"].agg(set).to_dict()
        self._fit(events, items)
        return self

    @abstractmethod
    def _fit(self, events: pd.DataFrame, items: pd.DataFrame) -> None: ...

    @abstractmethod
    def score(self, user_id: int, context: Context | None = None) -> np.ndarray:
        """Return score for every item (shape [n_items])."""

    def recommend(
        self,
        user_id: int,
        context: Context | None = None,
        k: int = 10,
        exclude_seen: bool = True,
    ) -> list[tuple[int, float]]:
        scores = self.score(user_id, context).astype(float).copy()
        if exclude_seen:
            for it in self.seen.get(user_id, ()):
                scores[it] = -np.inf
        top = np.argpartition(-scores, min(k, len(scores) - 1))[:k]
        top = top[np.argsort(-scores[top])]
        return [(int(i), float(scores[i])) for i in top if np.isfinite(scores[i])]
