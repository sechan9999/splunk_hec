"""Synthetic telco-style churn dataset with a known signal structure.

Churn log-odds are driven by: short tenure, month-to-month contract,
high monthly charges, many support tickets, declining usage, e-check payment.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

CONTRACTS = ["month-to-month", "one-year", "two-year"]
PAYMENTS = ["credit_card", "bank_transfer", "e_check"]
CONTRACT_EFFECT = {"month-to-month": 1.1, "one-year": -0.4, "two-year": -1.3}
PAYMENT_EFFECT = {"credit_card": -0.2, "bank_transfer": -0.1, "e_check": 0.6}

FEATURES_NUM = ["tenure_months", "monthly_charges", "support_tickets",
                "usage_trend", "num_services"]
FEATURES_CAT = ["contract", "payment_method"]


def generate(n: int = 6000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    tenure = rng.gamma(2.0, 14.0, n).clip(1, 72).round().astype(int)
    contract = rng.choice(CONTRACTS, size=n, p=[0.55, 0.25, 0.20])
    services = rng.integers(1, 7, size=n)
    charges = (20 + services * 14 + rng.normal(0, 8, n)).clip(20, 130).round(2)
    tickets = rng.poisson(1.2, n)
    usage_trend = rng.normal(0, 1, n).round(3)  # + growing, - declining

    logit = (
        -1.1
        - 0.045 * tenure
        + np.array([CONTRACT_EFFECT[c] for c in contract])
        + 0.018 * (charges - 70)
        + 0.35 * tickets
        - 0.55 * usage_trend
        + rng.normal(0, 0.6, n)
    )
    payment = rng.choice(PAYMENTS, size=n, p=[0.4, 0.3, 0.3])
    logit += np.array([PAYMENT_EFFECT[p] for p in payment])

    churn = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)

    return pd.DataFrame({
        "customer_id": np.arange(n),
        "tenure_months": tenure,
        "contract": contract,
        "payment_method": payment,
        "num_services": services,
        "monthly_charges": charges,
        "support_tickets": tickets,
        "usage_trend": usage_trend,
        "churn": churn,
    })
