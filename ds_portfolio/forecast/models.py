"""Forecasters + rolling-holdout backtest.

Baseline: seasonal naive (same week last year).
Model: Ridge regression on lag/Fourier/holiday/trend features,
recursive multi-step forecasting per store.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .data import HOLIDAYS


def _features(df: pd.DataFrame) -> pd.DataFrame:
    """Feature frame for one store's history (sorted by week).

    Only uses information available at forecast time: last year's sales
    (lag_52), calendar seasonality, planned holidays/promos, trend.
    """
    out = pd.DataFrame(index=df.index)
    out["lag_52"] = df["weekly_sales"].shift(52)
    woy = df["week"].dt.isocalendar().week.astype(float)
    out["sin1"] = np.sin(2 * np.pi * woy / 52.18)
    out["cos1"] = np.cos(2 * np.pi * woy / 52.18)
    out["sin2"] = np.sin(4 * np.pi * woy / 52.18)
    out["cos2"] = np.cos(4 * np.pi * woy / 52.18)
    for name in HOLIDAYS:
        out[f"hol_{name}"] = (df["holiday_name"] == name).astype(int)
    out["has_promo"] = df["has_promo"].astype(int)
    out["t"] = np.arange(len(df))
    return out


def seasonal_naive(history: pd.Series, horizon: int) -> np.ndarray:
    """Repeat the value from 52 weeks before each target week."""
    vals = history.to_numpy()
    return np.array([vals[len(vals) - 52 + h] if len(vals) - 52 + h < len(vals)
                     else vals[-52 + (h % 52)] for h in range(horizon)])


def ridge_forecast(train: pd.DataFrame, future: pd.DataFrame) -> np.ndarray:
    """Fit on train, directly predict len(future) weeks ahead.

    Trains in log space so multiplicative components (seasonality,
    holiday spikes, promos) become additive and linear. Direct (not
    recursive): every feature is known at forecast time, so multi-step
    errors don't compound.
    """
    full = pd.concat([train, future.assign(weekly_sales=np.nan)],
                     ignore_index=True)
    full["weekly_sales"] = np.log(full["weekly_sales"])
    feats = _features(full)

    train_mask = feats.notna().all(axis=1) & (feats.index < len(train))
    model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    model.fit(feats[train_mask], full.loc[train_mask, "weekly_sales"])

    return np.exp(model.predict(feats.iloc[len(train):]))


def wmae(y: np.ndarray, yhat: np.ndarray, holiday: np.ndarray) -> float:
    """Walmart-style weighted MAE: holiday weeks weigh 5x."""
    w = np.where(holiday, 5.0, 1.0)
    return float(np.sum(w * np.abs(y - yhat)) / np.sum(w))


def mape(y: np.ndarray, yhat: np.ndarray) -> float:
    return float(np.mean(np.abs((y - yhat) / y)) * 100)


def backtest(df: pd.DataFrame, horizon: int = 13) -> dict:
    """Hold out the last `horizon` weeks per store; compare both models.

    Returns {"metrics": DataFrame, "forecasts": DataFrame (long format)}.
    """
    rows, fc_frames = [], []
    for store, g in df.groupby("store"):
        g = g.sort_values("week").reset_index(drop=True)
        train, test = g.iloc[:-horizon], g.iloc[-horizon:]
        y = test["weekly_sales"].to_numpy()
        hol = test["is_holiday"].to_numpy()

        preds = {
            "seasonal_naive": seasonal_naive(train["weekly_sales"], horizon),
            "ridge": ridge_forecast(train, test.drop(columns="weekly_sales")),
        }
        for name, p in preds.items():
            rows.append({"store": store, "model": name,
                         "mape": round(mape(y, p), 2),
                         "wmae": round(wmae(y, p, hol), 0)})
            fc_frames.append(pd.DataFrame({
                "store": store, "week": test["week"].values,
                "model": name, "forecast": p, "actual": y}))

    metrics = pd.DataFrame(rows)
    summary = (metrics.groupby("model", as_index=False)[["mape", "wmae"]].mean()
                      .round({"mape": 2, "wmae": 0}))
    return {"metrics": metrics, "summary": summary,
            "forecasts": pd.concat(fc_frames, ignore_index=True)}
