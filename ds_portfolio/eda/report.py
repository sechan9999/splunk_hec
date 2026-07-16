"""Business-reporting aggregates over the cleaned orders frame."""
from __future__ import annotations

import pandas as pd


def business_report(df: pd.DataFrame) -> dict[str, pd.DataFrame | dict]:
    """Return KPI dict + report DataFrames for dashboards/exports."""
    kpis = {
        "total_revenue": float(df["revenue"].sum()),
        "orders": int(len(df)),
        "aov": float(df["revenue"].mean()),
        "avg_units": float(df["quantity"].mean()),
    }

    monthly = (df.set_index("order_date")
                 .resample("MS")["revenue"].sum()
                 .reset_index()
                 .rename(columns={"order_date": "month"}))

    by_category = (df.groupby("category", as_index=False)
                     .agg(revenue=("revenue", "sum"), orders=("order_id", "count"))
                     .sort_values("revenue", ascending=False))

    by_region_channel = (df.pivot_table(index="customer_region", columns="channel",
                                        values="revenue", aggfunc="sum")
                           .round(0).fillna(0))

    weekday = (df.assign(weekday=df["order_date"].dt.day_name())
                 .groupby("weekday", as_index=False)["revenue"].sum())
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday["weekday"] = pd.Categorical(weekday["weekday"], categories=order, ordered=True)
    weekday = weekday.sort_values("weekday")

    return {"kpis": kpis, "monthly": monthly, "by_category": by_category,
            "by_region_channel": by_region_channel, "weekday": weekday}
