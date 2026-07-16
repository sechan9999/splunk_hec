"""Walmart-style synthetic weekly store sales.

Components per store: base level, mild trend, annual seasonality (Fourier),
holiday spikes (Super Bowl, Thanksgiving, Christmas), promo markdowns, noise.
Weeks end on Friday, matching the Walmart Kaggle convention.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# (month, day) anchors; the containing week gets the spike
HOLIDAYS = {
    "super_bowl": ((2, 8), 1.25),
    "thanksgiving": ((11, 26), 1.80),
    "christmas": ((12, 24), 1.55),
}

# department -> (share of store base, holiday sensitivity, weekly trend %)
# heterogeneous by design: electronics spikes hard on holidays and grows,
# apparel barely reacts and declines — structure the store total blurs.
DEPTS = {
    "grocery":     (0.40, 1.30, 0.0005),
    "electronics": (0.25, 1.60, 0.0020),
    "apparel":     (0.20, 0.90, -0.0012),
    "home":        (0.15, 0.75, 0.0000),
}


def generate(n_weeks: int = 160, n_stores: int = 5, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    weeks = pd.date_range("2023-01-06", periods=n_weeks, freq="W-FRI")

    frames = []
    for store in range(1, n_stores + 1):
        base = rng.uniform(0.8e6, 2.2e6)
        trend = rng.uniform(-300, 900)  # per week
        t = np.arange(n_weeks)
        woy = weeks.isocalendar().week.to_numpy().astype(float)

        seasonal = (1
                    + 0.10 * np.sin(2 * np.pi * woy / 52.18)
                    + 0.05 * np.cos(4 * np.pi * woy / 52.18))

        holiday_mult = np.ones(n_weeks)
        is_holiday = np.zeros(n_weeks, dtype=bool)
        holiday_name = np.array([""] * n_weeks, dtype=object)
        for name, ((month, day), mult) in HOLIDAYS.items():
            anchor = pd.to_datetime([f"{y}-{month:02d}-{day:02d}" for y in weeks.year.unique()])
            for a in anchor:
                mask = np.asarray((weeks >= a - pd.Timedelta(days=6)) & (weeks <= a))
                holiday_mult[mask] = np.maximum(holiday_mult[mask], mult)
                holiday_name[mask] = name
                is_holiday |= mask

        promo = rng.random(n_weeks) < 0.15
        promo_mult = np.where(promo, rng.uniform(1.05, 1.20, n_weeks), 1.0)

        sales = ((base + trend * t) * seasonal * holiday_mult * promo_mult
                 * rng.lognormal(0, 0.03, n_weeks))

        frames.append(pd.DataFrame({
            "store": store,
            "week": weeks,
            "weekly_sales": sales.round(2),
            "is_holiday": is_holiday,
            "holiday_name": holiday_name,
            "has_promo": promo,
        }))

    return pd.concat(frames, ignore_index=True)


def generate_hierarchical(n_weeks: int = 160, n_stores: int = 5,
                          seed: int = 42) -> pd.DataFrame:
    """Store × department weekly sales, each dept an independent series.

    Depts differ in holiday sensitivity, trend direction, and — crucially —
    run their own promo calendars (markdowns are department decisions).
    A store-total model only sees an "any dept on promo" blur, which is
    what gives bottom-up forecasting its edge.
    """
    rng = np.random.default_rng(seed + 1)
    store_df = generate(n_weeks=n_weeks, n_stores=n_stores, seed=seed)

    frames = []
    for store, g in store_df.groupby("store"):
        g = g.sort_values("week").reset_index(drop=True)
        hol = g["is_holiday"].to_numpy()
        t = np.arange(len(g))
        # store total without its own promo effect: use as shared base shape
        base_shape = g["weekly_sales"].to_numpy()
        for dept, (share, hol_sens, growth) in DEPTS.items():
            hol_mult = np.where(hol, hol_sens, 1.0)
            trend = np.exp(growth * t)
            promo = rng.random(len(g)) < 0.15
            promo_mult = np.where(promo, rng.uniform(1.08, 1.30, len(g)), 1.0)
            noise = rng.lognormal(0, 0.05, len(g))
            d = g.copy()
            d["dept"] = dept
            d["has_promo"] = promo
            d["weekly_sales"] = (base_shape * share * hol_mult * trend
                                 * promo_mult * noise).round(2)
            frames.append(d)

    hier = pd.concat(frames, ignore_index=True)
    return hier[["store", "dept", "week", "weekly_sales",
                 "is_holiday", "holiday_name", "has_promo"]]
