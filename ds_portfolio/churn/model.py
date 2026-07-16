"""Churn classifiers: Logistic Regression baseline + Gradient Boosting."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (brier_score_loss, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score,
                             roc_curve)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .data import FEATURES_CAT, FEATURES_NUM


def _preprocessor() -> ColumnTransformer:
    return ColumnTransformer([
        ("num", StandardScaler(), FEATURES_NUM),
        ("cat", OneHotEncoder(handle_unknown="ignore"), FEATURES_CAT),
    ])


class ChurnModel:
    """Trains both models on a split, exposes metrics and per-customer scoring."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.models = {
            "logistic": Pipeline([("prep", _preprocessor()),
                                  ("clf", LogisticRegression(max_iter=1000))]),
            "gboost": Pipeline([("prep", _preprocessor()),
                                ("clf", GradientBoostingClassifier(random_state=seed))]),
        }
        self.metrics: dict[str, dict] = {}
        self.X_test: pd.DataFrame | None = None
        self.y_test: pd.Series | None = None

    def fit(self, df: pd.DataFrame) -> "ChurnModel":
        X = df[FEATURES_NUM + FEATURES_CAT]
        y = df["churn"]
        X_tr, X_te, y_tr, y_te = train_test_split(
            X, y, test_size=0.25, random_state=self.seed, stratify=y)
        self.X_test, self.y_test = X_te, y_te

        for name, model in self.models.items():
            model.fit(X_tr, y_tr)
            proba = model.predict_proba(X_te)[:, 1]
            pred = (proba >= 0.5).astype(int)
            fpr, tpr, _ = roc_curve(y_te, proba)
            self.metrics[name] = {
                "auc": roc_auc_score(y_te, proba),
                "precision": precision_score(y_te, pred),
                "recall": recall_score(y_te, pred),
                "f1": f1_score(y_te, pred),
                "brier": brier_score_loss(y_te, proba),
                "confusion": confusion_matrix(y_te, pred),
                "roc": (fpr, tpr),
                "proba": proba,
            }
        return self

    def calibration_table(self, name: str = "gboost", n_bins: int = 10) -> pd.DataFrame:
        """Reliability curve data: mean predicted vs observed churn per bin."""
        m = self.metrics[name]
        df = pd.DataFrame({"proba": m["proba"], "churn": self.y_test.values})
        df["bin"] = pd.cut(df["proba"], bins=np.linspace(0, 1, n_bins + 1),
                           include_lowest=True)
        out = (df.groupby("bin", observed=True)
                 .agg(mean_predicted=("proba", "mean"),
                      observed_rate=("churn", "mean"),
                      customers=("churn", "size"))
                 .reset_index(drop=True))
        return out.dropna()

    def cost_curve(self, name: str = "gboost", offer_cost: float = 20.0,
                   churn_loss: float = 400.0, save_rate: float = 0.35,
                   n_grid: int = 99) -> pd.DataFrame:
        """Expected cost per customer across thresholds.

        Everyone scored >= t gets a retention offer (cost `offer_cost`).
        A churner we miss (or fail to save: 1 - save_rate) costs `churn_loss`.
        """
        m = self.metrics[name]
        proba = m["proba"]
        y = self.y_test.to_numpy()
        n = len(y)
        rows = []
        for t in np.linspace(0.01, 0.99, n_grid):
            targeted = proba >= t
            tp = int((targeted & (y == 1)).sum())
            fp = int((targeted & (y == 0)).sum())
            fn = int((~targeted & (y == 1)).sum())
            cost = (offer_cost * (tp + fp)
                    + churn_loss * (fn + tp * (1 - save_rate)))
            rows.append({"threshold": t, "cost_per_customer": cost / n,
                         "targeted_pct": (tp + fp) / n})
        out = pd.DataFrame(rows)
        # references: never intervene / offer to everyone
        out.attrs["do_nothing"] = churn_loss * y.mean()
        out.attrs["target_all"] = offer_cost + churn_loss * y.mean() * (1 - save_rate)
        return out

    def optimal_threshold(self, **kwargs) -> dict:
        curve = self.cost_curve(**kwargs)
        best = curve.loc[curve["cost_per_customer"].idxmin()]
        return {"threshold": float(best["threshold"]),
                "cost_per_customer": float(best["cost_per_customer"]),
                "targeted_pct": float(best["targeted_pct"]),
                "do_nothing": float(curve.attrs["do_nothing"]),
                "target_all": float(curve.attrs["target_all"])}

    def lift_table(self, name: str = "gboost", n_bins: int = 10) -> pd.DataFrame:
        """Decile lift: how concentrated churners are in top-scored bins."""
        m = self.metrics[name]
        df = pd.DataFrame({"proba": m["proba"], "churn": self.y_test.values})
        df["decile"] = pd.qcut(df["proba"].rank(method="first"), n_bins,
                               labels=range(n_bins, 0, -1)).astype(int)
        base = df["churn"].mean()
        out = (df.groupby("decile", as_index=False)
                 .agg(customers=("churn", "size"), churners=("churn", "sum"),
                      churn_rate=("churn", "mean"))
                 .sort_values("decile"))
        out["lift"] = (out["churn_rate"] / base).round(2)
        return out

    def feature_importance(self, name: str = "gboost") -> pd.DataFrame:
        pipe = self.models[name]
        names = pipe.named_steps["prep"].get_feature_names_out()
        clf = pipe.named_steps["clf"]
        vals = (clf.feature_importances_ if hasattr(clf, "feature_importances_")
                else np.abs(clf.coef_[0]))
        return (pd.DataFrame({"feature": names, "importance": vals})
                  .sort_values("importance", ascending=False)
                  .reset_index(drop=True))

    def score_one(self, customer: dict, name: str = "gboost") -> float:
        X = pd.DataFrame([customer])[FEATURES_NUM + FEATURES_CAT]
        return float(self.models[name].predict_proba(X)[0, 1])
