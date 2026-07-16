"""Customer Churn Classifier — interactive demo page.

Logistic Regression vs Gradient Boosting on synthetic telco data.
Score a single customer live from the sidebar.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from ds_portfolio.churn import ChurnModel, generate
from ds_portfolio.churn.data import CONTRACTS, PAYMENTS

st.set_page_config(page_title="Churn Classifier", page_icon="📞",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
html, body, [data-testid="stApp"] { background: #11111b; }
.kpi-card { background: #1e1e2e; border-radius: 12px; padding: 16px 20px;
            border: 1px solid #313244; text-align: center; }
.kpi-value { color: #cdd6f4; font-size: 26px; font-weight: 700; }
.kpi-label { color: #a6adc8; font-size: 12px; }
</style>
""", unsafe_allow_html=True)

COLORS = {"logistic": "#74c7ec", "gboost": "#cba6f7"}


def dark(fig, h=340):
    fig.update_layout(paper_bgcolor="#1e1e2e", plot_bgcolor="#1e1e2e",
                      font_color="#cdd6f4", height=h,
                      margin=dict(l=40, r=20, t=50, b=40))
    return fig


@st.cache_resource
def train():
    df = generate()
    return df, ChurnModel().fit(df)


st.title("📞 Customer Churn Classifier")
df, cm = train()
st.caption(f"{len(df):,} synthetic telco customers · churn rate "
           f"{df['churn'].mean():.1%} · Logistic Regression vs Gradient Boosting")

# ── sidebar: score one customer ───────────────────────────────────────────────
st.sidebar.header("Score a customer")
customer = {
    "tenure_months": st.sidebar.slider("Tenure (months)", 1, 72, 8),
    "contract": st.sidebar.selectbox("Contract", CONTRACTS),
    "payment_method": st.sidebar.selectbox("Payment", PAYMENTS),
    "num_services": st.sidebar.slider("Services", 1, 6, 3),
    "monthly_charges": st.sidebar.slider("Monthly charges ($)", 20, 130, 80),
    "support_tickets": st.sidebar.slider("Support tickets", 0, 8, 2),
    "usage_trend": st.sidebar.slider("Usage trend (σ)", -3.0, 3.0, -0.5, 0.1),
}
risk = cm.score_one(customer)
color = "#f38ba8" if risk > 0.5 else "#f9e2af" if risk > 0.25 else "#a6e3a1"
st.sidebar.markdown(
    f'<div class="kpi-card"><div class="kpi-value" style="color:{color}">'
    f'{risk:.0%}</div><div class="kpi-label">churn risk (gboost)</div></div>',
    unsafe_allow_html=True)

# ── metric cards ─────────────────────────────────────────────────────────────
cols = st.columns(4)
for col, (name, metric) in zip(
        cols, [(n, k) for n in cm.metrics for k in ("auc", "f1")]):
    val = cm.metrics[name][metric]
    col.markdown(f'<div class="kpi-card"><div class="kpi-value" '
                 f'style="color:{COLORS[name]}">{val:.3f}</div>'
                 f'<div class="kpi-label">{name} · {metric.upper()}</div></div>',
                 unsafe_allow_html=True)
st.write("")

c1, c2 = st.columns(2)
with c1:
    fig = go.Figure()
    for name, m in cm.metrics.items():
        fpr, tpr = m["roc"]
        fig.add_trace(go.Scatter(x=fpr, y=tpr, name=f"{name} (AUC {m['auc']:.3f})",
                                 line=dict(color=COLORS[name], width=2)))
    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], showlegend=False,
                             line=dict(color="#45475a", dash="dash")))
    fig.update_layout(title="ROC curves", xaxis_title="FPR", yaxis_title="TPR")
    st.plotly_chart(dark(fig, 380), use_container_width=True)
with c2:
    lift = cm.lift_table()
    fig = px.bar(lift, x="decile", y="lift", text="lift",
                 color_discrete_sequence=["#cba6f7"],
                 title="Lift by score decile (1 = highest scores)")
    fig.add_hline(y=1.0, line_dash="dash", line_color="#45475a")
    st.plotly_chart(dark(fig, 380), use_container_width=True)

c3, c4 = st.columns(2)
with c3:
    imp = cm.feature_importance().head(8)
    imp["feature"] = (imp["feature"].str.replace("num__", "")
                                     .str.replace("cat__", ""))
    fig = px.bar(imp.iloc[::-1], x="importance", y="feature", orientation="h",
                 color_discrete_sequence=["#a6e3a1"],
                 title="Feature importance (gboost)")
    st.plotly_chart(dark(fig, 380), use_container_width=True)
with c4:
    conf = cm.metrics["gboost"]["confusion"]
    fig = go.Figure(go.Heatmap(z=conf, x=["pred stay", "pred churn"],
                               y=["actual stay", "actual churn"],
                               colorscale="Purp", texttemplate="%{z}"))
    fig.update_layout(title="Confusion matrix (gboost, threshold 0.5)")
    st.plotly_chart(dark(fig, 380), use_container_width=True)

st.info("💼 **Business read:** targeting the top 2 deciles captures most "
        "churners at >1.8× lift — the retention budget goes to ~20% of the "
        "base. Key drivers: month-to-month contract, short tenure, "
        "declining usage.")
