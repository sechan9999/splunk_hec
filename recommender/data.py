"""Synthetic e-commerce interaction generator.

Injects real structure so models have signal to learn:
- user segment -> category preference
- context (device, hour_bucket, weekend) -> category boost
- item base popularity (power-law)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

CATEGORIES = ["electronics", "fashion", "sports", "home", "beauty", "books", "toys", "grocery"]
SEGMENTS = ["tech", "fashion", "sports", "home", "budget"]
DEVICES = ["mobile", "desktop"]
HOUR_BUCKETS = ["morning", "day", "evening", "night"]

EVENT_WEIGHTS = {"view": 1.0, "click": 2.0, "add_to_cart": 3.0, "purchase": 5.0}
EVENT_TYPES = list(EVENT_WEIGHTS)
EVENT_PROBS = [0.62, 0.24, 0.09, 0.05]

# segment -> category affinity (rows sum to 1)
SEGMENT_AFFINITY = {
    "tech":    [0.60, 0.03, 0.05, 0.05, 0.02, 0.10, 0.07, 0.08],
    "fashion": [0.03, 0.58, 0.06, 0.05, 0.16, 0.04, 0.04, 0.04],
    "sports":  [0.06, 0.07, 0.60, 0.05, 0.03, 0.04, 0.06, 0.09],
    "home":    [0.05, 0.06, 0.04, 0.55, 0.06, 0.06, 0.07, 0.11],
    "budget":  [0.08, 0.11, 0.08, 0.11, 0.09, 0.15, 0.13, 0.25],
}

# (device, hour_bucket) -> category multiplier; 1.0 elsewhere
CONTEXT_BOOST = {
    ("mobile", "evening"):  {"fashion": 2.4, "sports": 2.0},
    ("mobile", "night"):    {"books": 2.2, "toys": 1.8},
    ("mobile", "morning"):  {"grocery": 2.4, "beauty": 1.8},
    ("desktop", "day"):     {"electronics": 2.4, "home": 1.8},
    ("desktop", "evening"): {"electronics": 1.8, "books": 1.6},
    ("desktop", "morning"): {"home": 2.0, "grocery": 1.6},
}


def generate(
    n_users: int = 1200,
    n_items: int = 300,
    n_events: int = 100_000,
    n_days: int = 90,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (users, items, events) DataFrames."""
    rng = np.random.default_rng(seed)

    users = pd.DataFrame({
        "user_id": np.arange(n_users),
        "segment": rng.choice(SEGMENTS, size=n_users),
    })

    items = pd.DataFrame({
        "item_id": np.arange(n_items),
        "category": rng.choice(CATEGORIES, size=n_items),
        "price_tier": rng.integers(1, 4, size=n_items),
        "base_popularity": rng.lognormal(0.0, 0.6, size=n_items),
    })

    # precompute per-category item lists and their popularity weights
    cat_items: dict[str, np.ndarray] = {}
    cat_pop: dict[str, np.ndarray] = {}
    for cat in CATEGORIES:
        mask = items["category"].to_numpy() == cat
        cat_items[cat] = items["item_id"].to_numpy()[mask]
        pop = items["base_popularity"].to_numpy()[mask]
        cat_pop[cat] = pop / pop.sum()

    seg_of_user = users["segment"].to_numpy()
    # heavy/light users (power-law activity)
    activity = rng.pareto(1.2, size=n_users) + 0.2
    user_p = activity / activity.sum()

    ev_user = rng.choice(n_users, size=n_events, p=user_p)
    ev_day = rng.integers(0, n_days, size=n_events)
    ev_device = rng.choice(DEVICES, size=n_events, p=[0.65, 0.35])
    ev_hour = rng.choice(HOUR_BUCKETS, size=n_events, p=[0.2, 0.3, 0.35, 0.15])
    ev_weekend = rng.random(n_events) < (2 / 7)
    ev_type = rng.choice(EVENT_TYPES, size=n_events, p=EVENT_PROBS)

    aff_matrix = np.array([SEGMENT_AFFINITY[s] for s in SEGMENTS])
    seg_idx = {s: i for i, s in enumerate(SEGMENTS)}

    ev_item = np.empty(n_events, dtype=np.int64)
    for i in range(n_events):
        probs = aff_matrix[seg_idx[seg_of_user[ev_user[i]]]].copy()
        boost = CONTEXT_BOOST.get((ev_device[i], ev_hour[i]))
        if boost:
            for cat, mult in boost.items():
                probs[CATEGORIES.index(cat)] *= mult
        probs /= probs.sum()
        cat = CATEGORIES[rng.choice(len(CATEGORIES), p=probs)]
        ev_item[i] = rng.choice(cat_items[cat], p=cat_pop[cat])

    events = pd.DataFrame({
        "user_id": ev_user,
        "item_id": ev_item,
        "event_type": ev_type,
        "day": ev_day,
        "device": ev_device,
        "hour_bucket": ev_hour,
        "is_weekend": ev_weekend,
    })
    events["weight"] = events["event_type"].map(EVENT_WEIGHTS)
    return users, items, events
