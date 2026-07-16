"""Synthetic retail orders with injected data-quality issues.

Issues injected (so the cleaning pipeline has real work to do):
- missing values (customer_region, unit_price)
- exact duplicate rows
- inconsistent category casing / whitespace
- negative or zero quantities
- extreme unit_price outliers (fat-finger x100)
- order_date stored as mixed-format strings
"""
from __future__ import annotations

import numpy as np
import pandas as pd

CATEGORIES = ["Electronics", "Fashion", "Home", "Grocery", "Sports", "Beauty"]
REGIONS = ["North", "South", "East", "West"]
CHANNELS = ["online", "store", "mobile"]

BASE_PRICE = {"Electronics": 240.0, "Fashion": 55.0, "Home": 90.0,
              "Grocery": 18.0, "Sports": 70.0, "Beauty": 32.0}


def generate_raw(n_orders: int = 8000, seed: int = 42) -> pd.DataFrame:
    """Return a raw orders DataFrame with realistic quality problems."""
    rng = np.random.default_rng(seed)

    cat = rng.choice(CATEGORIES, size=n_orders, p=[0.18, 0.22, 0.16, 0.24, 0.11, 0.09])
    qty = rng.integers(1, 6, size=n_orders)
    price = np.array([BASE_PRICE[c] for c in cat]) * rng.lognormal(0, 0.35, n_orders)

    # order dates over 18 months, weekend-heavy
    days = rng.integers(0, 548, size=n_orders)
    dates = pd.Timestamp("2025-01-01") + pd.to_timedelta(days, unit="D")

    df = pd.DataFrame({
        "order_id": np.arange(100000, 100000 + n_orders),
        "order_date": dates.strftime("%Y-%m-%d"),
        "category": cat,
        "customer_region": rng.choice(REGIONS, size=n_orders),
        "channel": rng.choice(CHANNELS, size=n_orders, p=[0.45, 0.35, 0.20]),
        "quantity": qty,
        "unit_price": price.round(2),
    })

    # -- inject issues ---------------------------------------------------
    idx = rng.permutation(n_orders)

    miss_region = idx[: int(n_orders * 0.06)]
    df.loc[miss_region, "customer_region"] = None

    miss_price = idx[int(n_orders * 0.06): int(n_orders * 0.09)]
    df.loc[miss_price, "unit_price"] = np.nan

    bad_case = idx[int(n_orders * 0.09): int(n_orders * 0.17)]
    df.loc[bad_case, "category"] = df.loc[bad_case, "category"].str.upper().str.pad(12)

    neg_qty = idx[int(n_orders * 0.17): int(n_orders * 0.19)]
    df.loc[neg_qty, "quantity"] = -df.loc[neg_qty, "quantity"]

    outlier = idx[int(n_orders * 0.19): int(n_orders * 0.20)]
    df.loc[outlier, "unit_price"] = df.loc[outlier, "unit_price"] * 100

    mixed_fmt = idx[int(n_orders * 0.20): int(n_orders * 0.28)]
    df.loc[mixed_fmt, "order_date"] = pd.to_datetime(
        df.loc[mixed_fmt, "order_date"]).dt.strftime("%m/%d/%Y")

    dupes = df.sample(n=int(n_orders * 0.03), random_state=seed)
    df = pd.concat([df, dupes], ignore_index=True)

    return df.sample(frac=1, random_state=seed).reset_index(drop=True)
