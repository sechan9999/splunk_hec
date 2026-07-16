"""Offline evaluation: temporal split, Recall@K, NDCG@K, catalog coverage."""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from .models.base import BaseRecommender, Context


def temporal_split(
    events: pd.DataFrame, train_end: int = 70, val_end: int = 80
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return (
        events[events["day"] < train_end],
        events[(events["day"] >= train_end) & (events["day"] < val_end)],
        events[events["day"] >= val_end],
    )


def build_ground_truth(
    train: pd.DataFrame, holdout: pd.DataFrame, min_weight: float = 2.0
) -> dict[int, set[int]]:
    """Per-user holdout positives (click+) excluding items already in train."""
    seen = train.groupby("user_id")["item_id"].agg(set).to_dict()
    pos = holdout[holdout["weight"] >= min_weight]
    truth: dict[int, set[int]] = {}
    for u, grp in pos.groupby("user_id"):
        new_items = set(grp["item_id"]) - seen.get(u, set())
        if new_items:
            truth[int(u)] = new_items
    return truth


def modal_context(holdout: pd.DataFrame) -> dict[int, Context]:
    """Each user's most frequent context in the holdout window."""
    ctx: dict[int, Context] = {}
    grouped = holdout.groupby(
        ["user_id", "device", "hour_bucket", "is_weekend"]
    ).size().reset_index(name="n")
    for u, grp in grouped.groupby("user_id"):
        row = grp.loc[grp["n"].idxmax()]
        ctx[int(u)] = Context(
            device=row["device"],
            hour_bucket=row["hour_bucket"],
            is_weekend=bool(row["is_weekend"]),
        )
    return ctx


def _ndcg_at_k(recs: list[int], truth: set[int], k: int) -> float:
    dcg = sum(1.0 / np.log2(r + 2) for r, item in enumerate(recs[:k]) if item in truth)
    idcg = sum(1.0 / np.log2(r + 2) for r in range(min(len(truth), k)))
    return dcg / idcg if idcg > 0 else 0.0


def evaluate(
    model: BaseRecommender,
    truth: dict[int, set[int]],
    contexts: dict[int, Context],
    k: int = 10,
) -> dict[str, float]:
    recalls, ndcgs = [], []
    recommended: set[int] = set()
    for u, pos in truth.items():
        recs = [i for i, _ in model.recommend(u, contexts.get(u), k=k)]
        recommended.update(recs)
        hits = len(set(recs) & pos)
        recalls.append(hits / min(len(pos), k))
        ndcgs.append(_ndcg_at_k(recs, pos, k))
    return {
        f"recall@{k}": float(np.mean(recalls)),
        f"ndcg@{k}": float(np.mean(ndcgs)),
        f"coverage@{k}": len(recommended) / model.n_items,
        "users": len(truth),
    }


def tune_hybrid_weights(
    hybrid, truth_val: dict[int, set[int]], ctx_val: dict[int, Context], k: int = 10
) -> tuple[float, float, float, float]:
    """Grid search blend weights on validation NDCG@K.

    Component scores are precomputed once per user, so each grid point is
    just a weighted sum — allowing a finer simplex grid (step 0.1) at a
    fraction of the old cost.
    """
    comp: dict[int, tuple] = {}
    for u in truth_val:
        c = hybrid.component_scores(u, ctx_val.get(u))
        stacked = np.stack([c["cf"], c["content"], c["popularity"], c["context"]])
        seen = np.fromiter(hybrid.seen.get(u, ()), dtype=int)
        comp[u] = (stacked, seen, u in hybrid.seen)

    def ndcg_for(w: tuple[float, ...]) -> float:
        scores = []
        for u, pos in truth_val.items():
            stacked, seen, warm = comp[u]
            s = (np.asarray(w) @ stacked if warm
                 else 0.6 * stacked[2] + 0.4 * stacked[3])
            if seen.size:
                s = s.copy()
                s[seen] = -np.inf
            top = np.argpartition(-s, k)[:k]
            recs = [int(i) for i in top[np.argsort(-s[top])]]
            scores.append(_ndcg_at_k(recs, pos, k))
        return float(np.mean(scores))

    grid = np.round(np.arange(0.0, 1.01, 0.1), 2)
    best, best_w = -1.0, hybrid.weights
    for w_cf, w_ct, w_pop in itertools.product(grid, grid, grid):
        w_ctx = round(1.0 - w_cf - w_ct - w_pop, 2)
        if w_ctx < 0:
            continue
        w = (float(w_cf), float(w_ct), float(w_pop), float(w_ctx))
        score = ndcg_for(w)
        if score > best:
            best, best_w = score, w
    hybrid.set_weights(best_w)
    return best_w
