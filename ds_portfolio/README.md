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

## v2 additions (follow-ups)

- **Churn**: reliability curve + Brier score (well calibrated — probabilities
  are priceable), and cost-based threshold optimization: with offer $20 /
  churn loss $400 / save rate 35%, optimal t*≈0.14 targets 58% of the base at
  **$82/customer vs $102 doing nothing** — the threshold is set by economics,
  not accuracy at 0.5.
- **Forecast**: split-conformal prediction intervals from rolling-origin
  out-of-sample residuals (90% PI → **92.3%** empirical coverage; in-sample
  residuals only reached 80%), and store×dept hierarchical forecasting where
  **bottom-up beats direct** (MAPE 5.84% vs 6.14%, WMAE $193k vs $200k)
  because departments run independent promo calendars the store total blurs.
- **Recommender**: see `recommender/README.md` §v3 — similarity-level
  CF+content blending experiment.

## Design notes

- **Synthetic-but-structured data**: every generator injects known signal
  (churn drivers, holiday spike sizes, quality issues) so model quality is
  measurable against ground truth.
- **Forecast model is direct, not recursive**: all features (lag-52,
  calendar, planned holidays/promos) are known at forecast time, so
  multi-step errors don't compound. Trained in log space so multiplicative
  seasonality/holiday effects become linear.
- Deps: pandas, numpy, scikit-learn, plotly, streamlit only.
