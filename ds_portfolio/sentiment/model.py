"""TF-IDF (word 1-2 grams) + Logistic Regression sentiment classifier.

Bigrams are what let a linear model handle negation ("not great") and
contrast — with unigrams alone "great" always votes positive.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (confusion_matrix, f1_score, roc_auc_score, roc_curve)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


class SentimentModel:
    def __init__(self, seed: int = 42, ngram_max: int = 2):
        self.seed = seed
        self.pipe = Pipeline([
            ("tfidf", TfidfVectorizer(ngram_range=(1, ngram_max), min_df=2,
                                      sublinear_tf=True)),
            ("clf", LogisticRegression(max_iter=1000, C=4.0)),
        ])
        self.metrics: dict = {}

    def fit(self, df: pd.DataFrame) -> "SentimentModel":
        X_tr, X_te, y_tr, y_te = train_test_split(
            df["text"], df["label"], test_size=0.25,
            random_state=self.seed, stratify=df["label"])
        self.pipe.fit(X_tr, y_tr)

        proba = self.pipe.predict_proba(X_te)[:, 1]
        pred = (proba >= 0.5).astype(int)
        fpr, tpr, _ = roc_curve(y_te, proba)
        self.metrics = {
            "accuracy": float((pred == y_te).mean()),
            "f1": f1_score(y_te, pred),
            "auc": roc_auc_score(y_te, proba),
            "confusion": confusion_matrix(y_te, pred),
            "roc": (fpr, tpr),
            "n_test": len(y_te),
            "errors": pd.DataFrame({"text": X_te, "label": y_te,
                                    "proba": proba})[pred != y_te],
        }
        return self

    def top_ngrams(self, n: int = 12) -> pd.DataFrame:
        """Strongest positive and negative n-gram coefficients."""
        vocab = self.pipe.named_steps["tfidf"].get_feature_names_out()
        coef = self.pipe.named_steps["clf"].coef_[0]
        order = np.argsort(coef)
        rows = ([{"ngram": vocab[i], "coef": coef[i], "polarity": "negative"}
                 for i in order[:n]]
                + [{"ngram": vocab[i], "coef": coef[i], "polarity": "positive"}
                   for i in order[-n:]])
        return pd.DataFrame(rows)

    def predict_one(self, text: str) -> dict:
        """Probability + per-ngram contributions for explanation."""
        proba = float(self.pipe.predict_proba([text])[0, 1])
        vec = self.pipe.named_steps["tfidf"].transform([text])
        coef = self.pipe.named_steps["clf"].coef_[0]
        vocab = self.pipe.named_steps["tfidf"].get_feature_names_out()
        idx = vec.nonzero()[1]
        contrib = (pd.DataFrame({
            "ngram": vocab[idx],
            "contribution": np.asarray(vec[0, idx].todense()).ravel() * coef[idx],
        }).sort_values("contribution"))
        return {"proba_positive": proba, "contributions": contrib}
