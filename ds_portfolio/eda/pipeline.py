"""Step-based cleaning pipeline with a per-step audit log."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class StepLog:
    step: str
    action: str
    rows_before: int
    rows_after: int
    cells_changed: int = 0


@dataclass
class CleaningPipeline:
    """Deterministic, auditable cleaning for the retail orders dataset."""
    iqr_k: float = 3.0
    logs: list[StepLog] = field(default_factory=list)

    def _log(self, step: str, action: str, before: int, after: int, changed: int = 0):
        self.logs.append(StepLog(step, action, before, after, changed))

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        n = len(df)

        # 1. normalize strings
        changed = int((df["category"] != df["category"].str.strip().str.title()).sum())
        df["category"] = df["category"].str.strip().str.title()
        self._log("normalize_text", "strip + title-case category", n, len(df), changed)

        # 2. parse mixed-format dates
        parsed = pd.to_datetime(df["order_date"], format="mixed")
        changed = int((df["order_date"].str.contains("/")).sum())
        df["order_date"] = parsed
        self._log("parse_dates", "mixed-format strings -> datetime64", len(df), len(df), changed)

        # 3. drop exact duplicates
        before = len(df)
        df = df.drop_duplicates()
        self._log("drop_duplicates", "exact duplicate rows removed", before, len(df))

        # 4. drop invalid quantities (returns handled elsewhere)
        before = len(df)
        df = df[df["quantity"] > 0]
        self._log("drop_invalid_qty", "quantity <= 0 removed", before, len(df))

        # 5. cap price outliers (IQR fence, per category)
        def _cap(g: pd.Series) -> pd.Series:
            q1, q3 = g.quantile([0.25, 0.75])
            hi = q3 + self.iqr_k * (q3 - q1)
            return g.clip(upper=hi)
        capped = df.groupby("category")["unit_price"].transform(_cap)
        changed = int((capped != df["unit_price"]).sum() - df["unit_price"].isna().sum())
        df["unit_price"] = capped
        self._log("cap_outliers", f"IQR fence (k={self.iqr_k}) per category", len(df), len(df), changed)

        # 6. impute missing
        n_price = int(df["unit_price"].isna().sum())
        df["unit_price"] = df["unit_price"].fillna(
            df.groupby("category")["unit_price"].transform("median"))
        n_region = int(df["customer_region"].isna().sum())
        df["customer_region"] = df["customer_region"].fillna("Unknown")
        self._log("impute_missing",
                  "price -> category median; region -> 'Unknown'",
                  len(df), len(df), n_price + n_region)

        # 7. derived column
        df["revenue"] = (df["quantity"] * df["unit_price"]).round(2)
        self._log("derive_revenue", "revenue = quantity * unit_price", len(df), len(df), len(df))

        return df.reset_index(drop=True)

    def log_frame(self) -> pd.DataFrame:
        return pd.DataFrame([vars(s) for s in self.logs])


def quality_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Column-level quality snapshot (missing %, dtype, cardinality)."""
    return pd.DataFrame({
        "dtype": df.dtypes.astype(str),
        "missing_pct": (df.isna().mean() * 100).round(2),
        "n_unique": df.nunique(),
    })
