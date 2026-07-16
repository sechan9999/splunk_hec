"""Weekly Sales Forecaster — interactive demo page.

Walmart-style weekly store sales; seasonal-naive baseline vs Ridge with
lag/Fourier/holiday features. 13-week holdout backtest per store.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from ds_portfolio.forecast import backtest, generate

st.set_page_config(page_title="Sales Forecast", page_icon="📈",
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

COLORS = {"actual": "#cdd6f4", "ridge": "#74c7ec", "seasonal_naive": "#f9e2af"}


def dark(fig, h=380):
    fig.update_layout(paper_bgcolor="#1e1e2e", plot_bgcolor="#1e1e2e",
                      font_color="#cdd6f4", height=h,
                      margin=dict(l=40, r=20, t=50, b=40))
    return fig


@st.cache_data
def run_backtest(horizon: int):
    df = generate()
    return df, backtest(df, horizon=horizon)


st.title("📈 Weekly Sales Forecaster")
st.caption("Walmart-style synthetic weekly store sales · seasonal-naive "
           "baseline vs Ridge (lag-52 + Fourier + holiday/promo, log space) · "
           "rolling holdout backtest, WMAE weighs holiday weeks 5×.")

horizon = st.sidebar.slider("Backtest horizon (weeks)", 8, 26, 13)
df, res = run_backtest(horizon)
store = st.sidebar.selectbox("Store", sorted(df["store"].unique()))

# ── summary cards ────────────────────────────────────────────────────────────
s = res["summary"].set_index("model")
cols = st.columns(4)
for col, (label, val) in zip(cols, [
        ("Ridge MAPE", f"{s.loc['ridge','mape']:.2f}%"),
        ("Naive MAPE", f"{s.loc['seasonal_naive','mape']:.2f}%"),
        ("Ridge WMAE", f"${s.loc['ridge','wmae']:,.0f}"),
        ("Naive WMAE", f"${s.loc['seasonal_naive','wmae']:,.0f}")]):
    col.markdown(f'<div class="kpi-card"><div class="kpi-value">{val}</div>'
                 f'<div class="kpi-label">{label} · avg over stores</div></div>',
                 unsafe_allow_html=True)
st.write("")

# ── store detail ─────────────────────────────────────────────────────────────
g = df[df["store"] == store].sort_values("week")
fc = res["forecasts"].query("store == @store")

fig = go.Figure()
hist = g.iloc[-horizon - 78:]
fig.add_trace(go.Scatter(x=hist["week"], y=hist["weekly_sales"], name="actual",
                         line=dict(color=COLORS["actual"], width=2)))
for model in ["seasonal_naive", "ridge"]:
    fm = fc[fc["model"] == model]
    fig.add_trace(go.Scatter(x=fm["week"], y=fm["forecast"], name=model,
                             line=dict(color=COLORS[model], width=2, dash="dot")))
for _, r in hist[hist["is_holiday"]].iterrows():
    fig.add_vline(x=r["week"], line_color="#45475a", line_dash="dash")
fig.update_layout(title=f"Store {store} — actual vs forecast "
                        f"(dashed verticals = holiday weeks)")
st.plotly_chart(dark(fig, 420), use_container_width=True)

c1, c2 = st.columns(2)
with c1:
    fig = px.bar(res["metrics"], x="store", y="wmae", color="model",
                 barmode="group",
                 color_discrete_map={"ridge": COLORS["ridge"],
                                     "seasonal_naive": COLORS["seasonal_naive"]},
                 title="WMAE by store (holiday weeks weigh 5×)")
    st.plotly_chart(dark(fig), use_container_width=True)
with c2:
    fm = fc[fc["model"] == "ridge"].copy()
    fm["error_pct"] = (fm["forecast"] / fm["actual"] - 1) * 100
    fig = px.bar(fm, x="week", y="error_pct",
                 color_discrete_sequence=[COLORS["ridge"]],
                 title=f"Ridge weekly error % — store {store}")
    fig.add_hline(y=0, line_color="#45475a")
    st.plotly_chart(dark(fig), use_container_width=True)

st.info("💼 **Business read:** the Ridge model roughly halves holiday-weighted "
        "error vs last-year-naive by learning separate spike sizes per holiday "
        "and a promo effect — that is safety-stock and staffing planning "
        "accuracy, exactly where forecast misses cost the most.")
