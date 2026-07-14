"""Hybrid contextual recommender.

score = w_cf*CF + w_ct*Content + w_pop*Popularity + w_ctx*ContextAffinity
- ContextAffinity: P(category | device, hour_bucket, weekend) from train counts,
  mapped to items of that category.
- Weights tuned externally (grid search on validation NDCG) via set_weights().
- Cold-start users fall back to Popularity + ContextAffinity.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import BaseRecommender, Context, minmax
from .content import ContentBasedRecommender
from .item_cf import ItemItemCFRecommender
from .popularity import PopularityRecommender


class HybridContextualRecommender(BaseRecommender):
    name = "hybrid_contextual"

    def __init__(self, weights: tuple[float, float, float, float] = (0.5, 0.2, 0.1, 0.2)) -> None:
        super().__init__()
        self.weights = weights  # (cf, content, pop, ctx)
        self.cf = ItemItemCFRecommender()
        self.content = ContentBasedRecommender()
        self.pop = PopularityRecommender()
        self.ctx_affinity: dict[tuple, np.ndarray] = {}
        self._global_cat: np.ndarray | None = None

    def set_weights(self, weights: tuple[float, float, float, float]) -> None:
        self.weights = weights

    def _fit(self, events: pd.DataFrame, items: pd.DataFrame) -> None:
        self.cf.fit(events, items)
        self.content.fit(events, items)
        self.pop.fit(events, items)

        cats = sorted(items["category"].unique())
        cat_idx = {c: i for i, c in enumerate(cats)}
        item_cat = np.zeros(self.n_items, dtype=int)
        item_cat[items["item_id"].to_numpy()] = [
            cat_idx[c] for c in items["category"].to_numpy()
        ]
        self._item_cat = item_cat
        n_cats = len(cats)

        ev_cat = item_cat[events["item_id"].to_numpy()]
        w = events["weight"].to_numpy()

        glob = np.zeros(n_cats)
        np.add.at(glob, ev_cat, w)
        self._global_cat = glob / glob.sum()

        keys = list(zip(events["device"], events["hour_bucket"], events["is_weekend"]))
        df = pd.DataFrame({"key": keys, "cat": ev_cat, "w": w})
        for key, grp in df.groupby("key"):
            counts = np.zeros(n_cats)
            np.add.at(counts, grp["cat"].to_numpy(), grp["w"].to_numpy())
            # lift over global distribution -> context-specific boost
            self.ctx_affinity[key] = (counts / counts.sum()) / (self._global_cat + 1e-9)

    def _ctx_scores(self, context: Context | None) -> np.ndarray:
        if context is None:
            return np.zeros(self.n_items)
        key = (context.device, context.hour_bucket, context.is_weekend)
        lift = self.ctx_affinity.get(key)
        if lift is None:
            return np.zeros(self.n_items)
        return lift[self._item_cat]

    def score(self, user_id: int, context: Context | None = None) -> np.ndarray:
        w_cf, w_ct, w_pop, w_ctx = self.weights
        pop_s = minmax(self.pop.score(user_id))
        ctx_s = minmax(self._ctx_scores(context))
        if user_id not in self.seen:  # cold start
            return 0.6 * pop_s + 0.4 * ctx_s
        cf_s = minmax(self.cf.score(user_id))
        ct_s = minmax(self.content.score(user_id))
        return w_cf * cf_s + w_ct * ct_s + w_pop * pop_s + w_ctx * ctx_s

    def explain(self, user_id: int, item_id: int, context: Context | None = None) -> dict:
        w_cf, w_ct, w_pop, w_ctx = self.weights
        parts = {
            "cf": w_cf * minmax(self.cf.score(user_id))[item_id],
            "content": w_ct * minmax(self.content.score(user_id))[item_id],
            "popularity": w_pop * minmax(self.pop.score(user_id))[item_id],
            "context": w_ctx * minmax(self._ctx_scores(context))[item_id],
        }
        return {k: round(float(v), 4) for k, v in parts.items()}
