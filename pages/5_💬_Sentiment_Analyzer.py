"""Text Sentiment Analyzer — interactive demo page.

TF-IDF bigrams + Logistic Regression on synthetic product reviews.
Type any review and see the prediction with per-ngram contributions.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from ds_portfolio.sentiment import SentimentModel, generate

st.set_page_config(page_title="Sentiment Analyzer", page_icon="💬",
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

POS, NEG = "#a6e3a1", "#f38ba8"


def dark(fig, h=360):
    fig.update_layout(paper_bgcolor="#1e1e2e", plot_bgcolor="#1e1e2e",
                      font_color="#cdd6f4", height=h,
                      margin=dict(l=40, r=20, t=50, b=40))
    return fig


# bump when SentimentModel's API changes: cache_resource survives
# hot-reloads on Streamlit Cloud, so stale instances would lack new methods
MODEL_VERSION = 1


@st.cache_resource
def train(version: int):
    df = generate()
    return df, SentimentModel().fit(df)


st.title("💬 Text Sentiment Analyzer")
df, sm = train(MODEL_VERSION)
m = sm.metrics
st.caption(f"{len(df):,} synthetic product reviews (negation + contrastive "
           "cases + 3% label noise) · TF-IDF word 1–2 grams + Logistic Regression")

cols = st.columns(4)
for col, (label, val) in zip(cols, [
        ("Accuracy", f"{m['accuracy']:.1%}"),
        ("F1", f"{m['f1']:.3f}"),
        ("ROC-AUC", f"{m['auc']:.3f}"),
        ("Test reviews", f"{m['n_test']:,}")]):
    col.markdown(f'<div class="kpi-card"><div class="kpi-value">{val}</div>'
                 f'<div class="kpi-label">{label}</div></div>',
                 unsafe_allow_html=True)
st.write("")

# ── live scoring ─────────────────────────────────────────────────────────────
st.subheader("Try it")
text = st.text_area("Review text",
                    "The keyboard looks beautiful, but it stopped working "
                    "after a week.", height=80)
if text.strip():
    r = sm.predict_one(text)
    p = r["proba_positive"]
    verdict = "POSITIVE" if p >= 0.5 else "NEGATIVE"
    color = POS if p >= 0.5 else NEG
    c1, c2 = st.columns([1, 3])
    with c1:
        st.markdown(f'<div class="kpi-card"><div class="kpi-value" '
                    f'style="color:{color}">{verdict}</div>'
                    f'<div class="kpi-label">P(positive) = {p:.1%}</div></div>',
                    unsafe_allow_html=True)
    with c2:
        contrib = r["contributions"]
        contrib = contrib[contrib["contribution"].abs() > 1e-4]
        if len(contrib):
            fig = px.bar(contrib, x="contribution", y="ngram", orientation="h",
                         color=(contrib["contribution"] > 0).map(
                             {True: "positive", False: "negative"}),
                         color_discrete_map={"positive": POS, "negative": NEG},
                         title="Why: per-ngram contribution to the score")
            fig.update_layout(showlegend=False,
                              height=max(220, 26 * len(contrib) + 90))
            st.plotly_chart(dark(fig, max(220, 26 * len(contrib) + 90)),
                            use_container_width=True)

# ── model internals ──────────────────────────────────────────────────────────
c1, c2 = st.columns(2)
with c1:
    top = sm.top_ngrams(10)
    fig = px.bar(top, x="coef", y="ngram", orientation="h", color="polarity",
                 color_discrete_map={"positive": POS, "negative": NEG},
                 title="Strongest learned n-grams")
    fig.update_layout(showlegend=False)
    st.plotly_chart(dark(fig, 480), use_container_width=True)
with c2:
    conf = m["confusion"]
    fig = go.Figure(go.Heatmap(z=conf, x=["pred neg", "pred pos"],
                               y=["actual neg", "actual pos"],
                               colorscale="Greens", texttemplate="%{z}"))
    fig.update_layout(title="Confusion matrix (threshold 0.5)")
    st.plotly_chart(dark(fig), use_container_width=True)

    st.markdown("**Hardest misclassified reviews**")
    errs = m["errors"].copy()
    errs["P(pos)"] = errs["proba"].round(3)
    st.dataframe(errs[["text", "sentiment_true", "P(pos)"]]
                 if "sentiment_true" in errs else
                 errs[["text", "label", "P(pos)"]],
                 use_container_width=True, hide_index=True, height=180)

st.info("💼 **NLP read:** bigrams are what let a linear model handle negation "
        "— with unigrams alone, *great* in “not great at all” votes positive. "
        "Most remaining errors are the 3% injected label noise: the model "
        "can't (and shouldn't) fit mislabeled reviews.")
