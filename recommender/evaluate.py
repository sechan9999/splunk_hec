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
    """Grid search all four blend weights on validation NDCG@K."""
    grid = [0.0, 0.1, 0.2, 0.4, 0.6]
    best, best_w = -1.0, hybrid.weights
    seen_norm: set[tuple] = set()
    for w_cf, w_ct, w_pop, w_ctx in itertools.product(grid, grid, grid, grid):
        total = w_cf + w_ct + w_pop + w_ctx
        if total == 0:
            continue
        w = (w_cf / total, w_ct / total, w_pop / total, w_ctx / total)
        key = tuple(round(x, 6) for x in w)
        if key in seen_norm:
            continue
        seen_norm.add(key)
        hybrid.set_weights(w)
        score = evaluate(hybrid, truth_val, ctx_val, k=k)[f"ndcg@{k}"]
        if score > best:
            best, best_w = score, w
    hybrid.set_weights(best_w)
    return best_w
