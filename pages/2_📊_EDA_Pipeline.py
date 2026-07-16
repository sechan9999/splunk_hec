"""EDA & Data-Cleaning Pipeline — interactive demo page.

Raw retail orders (with injected quality issues) -> auditable cleaning
pipeline -> business report. Adjust the outlier fence and watch the
audit log change.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from ds_portfolio.eda import CleaningPipeline, business_report, generate_raw
from ds_portfolio.eda.pipeline import quality_summary

st.set_page_config(page_title="EDA Pipeline", page_icon="📊",
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

ACCENT = "#74c7ec"
PALETTE = ["#74c7ec", "#cba6f7", "#a6e3a1", "#f9e2af", "#f38ba8", "#fab387"]


def dark(fig, h=340):
    fig.update_layout(paper_bgcolor="#1e1e2e", plot_bgcolor="#1e1e2e",
                      font_color="#cdd6f4", height=h,
                      margin=dict(l=40, r=20, t=50, b=40))
    return fig


@st.cache_data
def load_raw():
    return generate_raw()


@st.cache_data
def clean(iqr_k: float):
    pipe = CleaningPipeline(iqr_k=iqr_k)
    df = pipe.run(load_raw())
    return df, pipe.log_frame()


st.title("📊 EDA & Data-Cleaning Pipeline")
st.caption("Synthetic retail orders with injected quality issues → step-based "
           "cleaning with an audit log → business report.")

iqr_k = st.sidebar.slider("Outlier fence (IQR × k)", 1.5, 6.0, 3.0, 0.5)

raw = load_raw()
df, log = clean(iqr_k)

tab_quality, tab_report = st.tabs(["🧹 Data Quality & Cleaning", "📈 Business Report"])

with tab_quality:
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("Raw quality snapshot")
        st.dataframe(quality_summary(raw), use_container_width=True)
        st.caption(f"raw rows: **{len(raw):,}** → clean rows: **{len(df):,}**")
    with c2:
        st.subheader("Cleaning audit log")
        st.dataframe(log, use_container_width=True, hide_index=True)

    st.subheader("Unit price distribution — before vs after")
    c3, c4 = st.columns(2)
    with c3:
        fig = px.histogram(raw, x="unit_price", nbins=60,
                           color_discrete_sequence=["#f38ba8"], log_y=True,
                           title="Raw (fat-finger outliers, log scale)")
        st.plotly_chart(dark(fig), use_container_width=True)
    with c4:
        fig = px.histogram(df, x="unit_price", nbins=60,
                           color_discrete_sequence=[ACCENT], log_y=True,
                           title="Cleaned (log scale)")
        st.plotly_chart(dark(fig), use_container_width=True)

with tab_report:
    rep = business_report(df)
    k = rep["kpis"]
    cols = st.columns(4)
    for col, (label, val) in zip(cols, [
            ("Total Revenue", f"${k['total_revenue']:,.0f}"),
            ("Orders", f"{k['orders']:,}"),
            ("Avg Order Value", f"${k['aov']:,.2f}"),
            ("Avg Units / Order", f"{k['avg_units']:.2f}")]):
        col.markdown(f'<div class="kpi-card"><div class="kpi-value">{val}</div>'
                     f'<div class="kpi-label">{label}</div></div>',
                     unsafe_allow_html=True)
    st.write("")

    c1, c2 = st.columns([3, 2])
    with c1:
        fig = px.line(rep["monthly"], x="month", y="revenue", markers=True,
                      color_discrete_sequence=[ACCENT], title="Monthly revenue")
        st.plotly_chart(dark(fig), use_container_width=True)
    with c2:
        fig = px.bar(rep["by_category"], x="revenue", y="category",
                     orientation="h", color="category",
                     color_discrete_sequence=PALETTE, title="Revenue by category")
        fig.update_layout(showlegend=False)
        st.plotly_chart(dark(fig), use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        pivot = rep["by_region_channel"]
        fig = go.Figure(go.Heatmap(z=pivot.values, x=list(pivot.columns),
                                   y=list(pivot.index), colorscale="Teal"))
        fig.update_layout(title="Revenue: region × channel")
        st.plotly_chart(dark(fig), use_container_width=True)
    with c4:
        fig = px.bar(rep["weekday"], x="weekday", y="revenue",
                     color_discrete_sequence=["#cba6f7"], title="Revenue by weekday")
        st.plotly_chart(dark(fig), use_container_width=True)
