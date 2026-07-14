"""Time-decayed popularity baseline. Also serves as cold-start fallback."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import BaseRecommender, Context


class PopularityRecommender(BaseRecommender):
    name = "popularity"

    def __init__(self, decay: float = 0.03) -> None:
        super().__init__()
        self.decay = decay
        self.pop: np.ndarray | None = None

    def _fit(self, events: pd.DataFrame, items: pd.DataFrame) -> None:
        max_day = events["day"].max()
        decayed = events["weight"].to_numpy() * np.exp(
            -self.decay * (max_day - events["day"].to_numpy())
        )
        self.pop = np.zeros(self.n_items)
        np.add.at(self.pop, events["item_id"].to_numpy(), decayed)

    def score(self, user_id: int, context: Context | None = None) -> np.ndarray:
        return self.pop.copy()
