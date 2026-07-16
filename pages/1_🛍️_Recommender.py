"""Hybrid Recommender — interactive demo page.

Blends CF + content + popularity + context; adjust the weights live and
watch the ranking change. Model trains once per container (cached).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from recommender.data import generate
from recommender.models import HybridContextualRecommender
from recommender.models.base import Context

st.set_page_config(page_title="Hybrid Recommender", page_icon="🛍️",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
html, body, [data-testid="stApp"] { background: #11111b; }
.rec-card {
    background: #1e1e2e; border-radius: 12px; padding: 14px 18px;
    border: 1px solid #313244; margin-bottom: 10px;
}
.rec-head { color: #cdd6f4; font-size: 15px; font-weight: 600; }
.rec-cat  { color: #a6adc8; font-size: 12px; }
</style>
""", unsafe_allow_html=True)

# host app palette (catppuccin) mapped to the four signals
SIG_COLORS = {"cf": "#74c7ec", "content": "#a6e3a1",
              "popularity": "#f9e2af", "context": "#cba6f7"}
SIG_LABELS = {"cf": "Collaborative", "content": "Content",
              "popularity": "Popularity", "context": "Context"}


# bump when model classes change: cache_resource survives hot-reloads on
# Streamlit Cloud, so stale instances would keep the old behavior/methods
MODEL_VERSION = 3


@st.cache_resource(show_spinner="Training recommender (one-time per session)...")
def load_model(version: int):
    users, items, events = generate()
    model = HybridContextualRecommender().fit(events, items)
    meta = items.set_index("item_id")[["category", "price_tier"]].to_dict("index")
    counts = events["user_id"].value_counts()
    sample = {}
    for _, row in users.iterrows():
        u, seg = int(row["user_id"]), row["segment"]
        if seg not in sample and 10 <= int(counts.get(u, 0)) <= 40:
            sample[seg] = u
    top_cats = {}
    for seg, u in sample.items():
        hist = events[events["user_id"] == u].copy()
        hist["category"] = hist["item_id"].map(lambda i: meta[i]["category"])
        top_cats[u] = (hist.groupby("category")["weight"].sum()
                       .sort_values(ascending=False).head(3).index.tolist())
    return model, meta, sample, top_cats


model, meta, sample, top_cats = load_model(MODEL_VERSION)

st.title("🛍️ Hybrid Recommender")
st.caption("User behavior + product data + context signals, blended into one ranking. "
           "Real model output — retrained live if you touch the weights.")

# ── Sidebar controls ──────────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("Who & when")
    user_options = {f"{seg} shopper (u{u})": u for seg, u in sorted(sample.items())}
    user_options["🆕 new user (cold start)"] = -1
    user_label = st.selectbox("User", list(user_options))
    user_id = user_options[user_label]

    device = st.radio("Device", ["mobile", "desktop"], horizontal=True)
    hour_bucket = st.select_slider("Time of day",
                                   ["morning", "day", "evening", "night"],
                                   value="evening")
    weekend = st.toggle("Weekend", value=False)
    k = st.slider("How many items", 3, 15, 8)

    st.divider()
    st.subheader("Blend weights")
    st.caption("run_eval tunes these automatically; here you can play.")
    w_cf = st.slider("Collaborative", 0.0, 1.0, 0.5, 0.05)
    w_ct = st.slider("Content", 0.0, 1.0, 0.2, 0.05)
    w_pop = st.slider("Popularity", 0.0, 1.0, 0.1, 0.05)
    w_ctx = st.slider("Context", 0.0, 1.0, 0.2, 0.05)

total = w_cf + w_ct + w_pop + w_ctx or 1.0
weights = (w_cf / total, w_ct / total, w_pop / total, w_ctx / total)
model.set_weights(weights)

ctx = Context(device, hour_bucket, weekend)
uid = 999_999 if user_id == -1 else user_id
recs = model.recommend(uid, ctx, k=k)

# ── Main: recommendations ─────────────────────────────────────────────────────
left, right = st.columns([3, 2], gap="large")

with left:
    st.subheader(f"Top {len(recs)} for {user_label}")
    if user_id == -1:
        st.info("No history — cold-start fallback: 0.6 · popularity + 0.4 · context affinity.")
    elif top_cats.get(uid):
        st.caption(f"History skews toward **{', '.join(top_cats[uid])}**")

    for rank, (item_id, score) in enumerate(recs, 1):
        m = meta[item_id]
        st.markdown(
            f'<div class="rec-card"><span class="rec-head">#{rank} · item {item_id} '
            f'· {score:.3f}</span><br><span class="rec-cat">{m["category"]} · '
            f'price tier {m["price_tier"]}</span></div>',
            unsafe_allow_html=True,
        )

with right:
    st.subheader("Why these items?")
    if user_id == -1:
        st.caption("Cold-start users have no per-signal breakdown — "
                   "popularity and context only.")
    else:
        rows = []
        for item_id, _ in recs:
            reason = model.explain(uid, item_id, ctx)
            for sig, val in reason.items():
                rows.append({"item": f"item {item_id}", "signal": sig, "value": val})
        df = pd.DataFrame(rows)
        fig = go.Figure()
        for sig in ["cf", "content", "popularity", "context"]:
            sub = df[df["signal"] == sig]
            fig.add_bar(y=sub["item"], x=sub["value"], name=SIG_LABELS[sig],
                        orientation="h", marker_color=SIG_COLORS[sig])
        fig.update_layout(
            barmode="stack", height=max(300, 42 * len(recs)),
            paper_bgcolor="#11111b", plot_bgcolor="#11111b",
            font_color="#cdd6f4", legend=dict(orientation="h", y=1.12),
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis=dict(gridcolor="#313244"), yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(fig, use_container_width=True)

# ── Offline metrics ───────────────────────────────────────────────────────────
st.divider()
st.subheader("Offline evaluation (temporal holdout, K=10)")
mdf = pd.DataFrame({
    "model": ["popularity", "item_cf (BM25)", "content", "sim_blend (α=0.9)",
              "hybrid_contextual"],
    "NDCG@10": [0.058, 0.120, 0.078, 0.119, 0.117],
    "Recall@10": [0.103, 0.194, 0.149, 0.196, 0.195],
    "Coverage@10": [0.30, 0.92, 0.72, 0.93, 0.77],
})
c1, c2 = st.columns([3, 2], gap="large")
with c1:
    fig2 = go.Figure()
    for metric, color in [("NDCG@10", "#74c7ec"), ("Recall@10", "#a6e3a1")]:
        fig2.add_bar(x=mdf["model"], y=mdf[metric], name=metric, marker_color=color)
    fig2.update_layout(
        barmode="group", height=320,
        paper_bgcolor="#11111b", plot_bgcolor="#11111b", font_color="#cdd6f4",
        legend=dict(orientation="h", y=1.15), margin=dict(l=10, r=10, t=10, b=10),
        yaxis=dict(gridcolor="#313244"),
    )
    st.plotly_chart(fig2, use_container_width=True)
with c2:
    st.dataframe(mdf.set_index("model"), use_container_width=True)
    st.caption("v2: BM25-weighted CF (+60% CF NDCG) + rank-percentile fusion. "
               "v3: sim_blend fuses CF + content at the *similarity matrix* "
               "level (α=0.9) — best recall & coverage. "
               "Weights grid-searched on a validation window (days 70–80), "
               "reported on test (days 80–90) — no leakage.")
