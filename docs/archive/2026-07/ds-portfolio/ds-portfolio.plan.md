# Plan: ds-portfolio (EDA Pipeline · Churn Classifier · Sales Forecaster)

## Goal
Three self-contained, interview-ready DS portfolio modules in `ds_portfolio/`,
each with a synthetic-data generator (reproducible, no external downloads),
a core pipeline/model, an offline eval CLI, and a Streamlit demo page.

## Scope
1. **EDA & data-cleaning pipeline** (`ds_portfolio/eda`)
   - Raw retail orders with injected quality issues (missing, dupes, bad casing,
     negative qty, price outliers, string dates)
   - Step-based cleaning pipeline with per-step audit log
   - Business report: KPIs, monthly revenue, category/region breakdowns
2. **Customer churn classifier** (`ds_portfolio/churn`)
   - Telco-style features (tenure, contract, charges, tickets, usage trend)
   - Logistic Regression + Gradient Boosting (scikit-learn)
   - Metrics: ROC-AUC, PR, confusion matrix, lift by decile, feature importance
3. **Weekly sales forecaster** (`ds_portfolio/forecast`)
   - Walmart-style weekly store sales: trend + annual seasonality + holiday
     spikes + promos
   - Baseline seasonal-naive (t-52) vs Ridge with lag/Fourier/holiday features
   - Rolling-origin backtest; MAPE + holiday-weighted MAE (WMAE)

## Non-goals
- Real datasets, deep learning, hyperparameter search, model persistence.

## Success criteria
- Each `run.py` executes cleanly; churn AUC > 0.80; Ridge beats seasonal-naive
  on WMAE; cleaning pipeline removes 100% of injected dupes/invalid rows.
- 3 Streamlit pages deploy on Streamlit Cloud (deps: + scikit-learn only).
