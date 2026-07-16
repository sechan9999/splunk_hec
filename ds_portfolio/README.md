# DS Portfolio Modules

Three self-contained, interview-ready data science projects. Each ships a
reproducible synthetic-data generator (no downloads), a core pipeline/model,
an offline eval CLI, and a Streamlit demo page.

| Module | What it shows | Demo page | CLI |
|---|---|---|---|
| `eda/` | Auditable data-cleaning pipeline + business report (KPIs, monthly revenue, category/region breakdowns) | `pages/2_📊_EDA_Pipeline.py` | `python ds_portfolio/eda/run.py` |
| `churn/` | Logistic Regression vs Gradient Boosting churn classifier — ROC-AUC, decile lift, feature importance, live scoring | `pages/3_📞_Churn_Classifier.py` | `python ds_portfolio/churn/run.py` |
| `forecast/` | Walmart-style weekly sales — seasonal-naive baseline vs Ridge (lag-52 + Fourier + holiday/promo, log space), WMAE backtest | `pages/4_📈_Sales_Forecast.py` | `python ds_portfolio/forecast/run.py` |
| `sentiment/` | TF-IDF bigram + Logistic Regression review classifier — handles negation & contrastive clauses, per-ngram explanations | `pages/5_💬_Sentiment_Analyzer.py` | `python ds_portfolio/sentiment/run.py` |

## Headline results (defaults, seed=42)

- **EDA**: removes 100% of injected duplicates and invalid rows; audit log
  records every action with row/cell counts.
- **Churn**: logistic AUC **0.811**; top decile lift **2.6×** (top 2 deciles
  capture the bulk of churners).
- **Forecast**: Ridge MAPE **3.4%** vs naive **5.6%**; holiday-weighted WMAE
  **~$74k** vs **~$122k** (13-week holdout, 5 stores).
- **Sentiment**: accuracy/F1/AUC **0.965** on 1,000 held-out reviews with 3%
  injected label noise; negated and contrastive phrases classified correctly.

## Design notes

- **Synthetic-but-structured data**: every generator injects known signal
  (churn drivers, holiday spike sizes, quality issues) so model quality is
  measurable against ground truth.
- **Forecast model is direct, not recursive**: all features (lag-52,
  calendar, planned holidays/promos) are known at forecast time, so
  multi-step errors don't compound. Trained in log space so multiplicative
  seasonality/holiday effects become linear.
- Deps: pandas, numpy, scikit-learn, plotly, streamlit only.
