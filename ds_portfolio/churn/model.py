"""Churn classifiers: Logistic Regression baseline + Gradient Boosting."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (confusion_matrix, f1_score, precision_score,
                             recall_score, roc_auc_score, roc_curve)
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
                "confusion": confusion_matrix(y_te, pred),
                "roc": (fpr, tpr),
                "proba": proba,
            }
        return self

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
