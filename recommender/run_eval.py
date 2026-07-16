"""Train all models, tune hybrid on validation, report test metrics.

Usage: python -m recommender.run_eval
"""
from __future__ import annotations

import time

import pandas as pd

from .data import generate
from .evaluate import (
    build_ground_truth, evaluate, modal_context, temporal_split, tune_hybrid_weights,
)
from .models import (
    ContentBasedRecommender, HybridContextualRecommender,
    ItemItemCFRecommender, PopularityRecommender, SimBlendRecommender,
)
from .models.sim_blend import tune_alpha


def main(k: int = 10) -> pd.DataFrame:
    print("Generating synthetic data...")
    users, items, events = generate()
    train, val, test = temporal_split(events)
    print(f"  events: train={len(train):,} val={len(val):,} test={len(test):,}")

    truth_val = build_ground_truth(train, val)
    truth_test = build_ground_truth(train, test)
    ctx_val = modal_context(val)
    ctx_test = modal_context(test)
    print(f"  eval users: val={len(truth_val)} test={len(truth_test)}")

    models = [
        PopularityRecommender(),
        ItemItemCFRecommender(),
        ContentBasedRecommender(),
    ]
    rows = []
    for m in models:
        t0 = time.perf_counter()
        m.fit(train, items)
        metrics = evaluate(m, truth_test, ctx_test, k=k)
        metrics["fit_s"] = round(time.perf_counter() - t0, 2)
        rows.append({"model": m.name, **metrics})

    blend = SimBlendRecommender()
    t0 = time.perf_counter()
    blend.fit(train, items)
    a = tune_alpha(blend, evaluate, truth_val, ctx_val, k=k)
    print(f"  sim_blend alpha (cf share of similarity): {a}")
    metrics = evaluate(blend, truth_test, ctx_test, k=k)
    metrics["fit_s"] = round(time.perf_counter() - t0, 2)
    rows.append({"model": blend.name, **metrics})

    hybrid = HybridContextualRecommender()
    t0 = time.perf_counter()
    hybrid.fit(train, items)
    w = tune_hybrid_weights(hybrid, truth_val, ctx_val, k=k)
    print(f"  hybrid weights (cf, content, pop, ctx): {tuple(round(x, 3) for x in w)}")
    metrics = evaluate(hybrid, truth_test, ctx_test, k=k)
    metrics["fit_s"] = round(time.perf_counter() - t0, 2)
    rows.append({"model": hybrid.name, **metrics})

    df = pd.DataFrame(rows).set_index("model")
    with pd.option_context("display.float_format", "{:.4f}".format):
        print("\n=== Test metrics (temporal holdout, K=%d) ===" % k)
        print(df.to_string())
    return df


if __name__ == "__main__":
    main()
