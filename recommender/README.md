# Hybrid Recommender System

Combines **user behavior** (implicit feedback), **product data** (category/price features),
and **contextual signals** (device, time of day, weekend) into a tunable hybrid ranker,
with an offline evaluation harness and a FastAPI serving layer.

## Quickstart

```bash
# offline evaluation (trains all models, tunes hybrid, prints comparison table)
python -m recommender.run_eval

# unit tests
python -m pytest tests/test_recommender.py -q

# serving API
uvicorn recommender.service:app --port 8100
curl -X POST localhost:8100/recommend -H "Content-Type: application/json" \
  -d '{"user_id": 42, "device": "mobile", "hour_bucket": "evening", "k": 5}'
```

Dependencies: `numpy`, `pandas`, `fastapi` (no sklearn required).

## Architecture

```
events (view/click/cart/purchase + context)
        │
        ├── PopularityRecommender   time-decayed popularity (baseline + cold-start)
        ├── ItemItemCFRecommender   item-item cosine CF, shrinkage, top-N pruning
        ├── ContentBasedRecommender item features × interaction-weighted user profile
        └── ContextAffinity         P(category | device, hour, weekend) lift vs global
                │
        HybridContextualRecommender
        score = w_cf·CF + w_ct·Content + w_pop·Pop + w_ctx·Context
        (weights tuned by grid search on validation NDCG@10)
                │
        FastAPI /recommend  → top-K + per-item reason breakdown
```

## Offline results (temporal holdout, K=10)

| model | recall@10 | ndcg@10 | coverage@10 |
|---|---|---|---|
| popularity | 0.103 | 0.058 | 0.30 |
| item_cf | 0.142 | 0.075 | 0.99 |
| content | 0.149 | 0.078 | 0.72 |
| **hybrid_contextual** | **0.186** | **0.114** | 0.74 |

Hybrid ≈ **2× NDCG vs popularity baseline** with 2.5× catalog coverage.
Tuned weights on this data: content 0.55, popularity 0.36, context 0.09
(CF contribution varies by seed/scale — the tuner adapts automatically).

## Evaluation protocol

- **Temporal split**: days 0–70 train / 70–80 validation (weight tuning) / 80–90 test — no leakage.
- Ground truth: click-or-stronger events on items *not* seen in train.
- Metrics: Recall@K, NDCG@K, catalog coverage@K.

## Key design decisions

- **Cold start**: users with no history get `0.6·popularity + 0.4·context affinity`.
- **Explainability**: `/recommend` returns per-item `reason` (cf/content/popularity/context
  contributions) — useful for debugging, trust, and merchandising review.
- **Context as lift, not count**: `P(cat|ctx) / P(cat)` so context only reorders where it
  genuinely deviates from global behavior.
- Demo fits on synthetic data at startup; the generator injects real structure
  (segment→category preference, context→category boosts) so models have learnable signal.

## Production path (engineering handoff)

1. **Batch training**: replace startup-fit with a daily job that trains and writes artifacts
   (similarity matrix, profiles, affinity table); service loads artifacts only.
2. **Feedback loop**: log impressions + clicks with request context → retraining data;
   watch for position bias (log rank, use inverse-propensity weighting later).
3. **Experimentation**: A/B or interleaving; guardrails = CTR, coverage, latency p99 < 50 ms.
4. **Scale**: swap dense matrices for sparse (`scipy.sparse`), ANN retrieval (FAISS) at
   >100K items; candidate-generation + ranking split.
5. **Model roadmap**: ALS/BPR embeddings → two-tower retrieval + GBDT ranker with context
   features → sequence models (SASRec) for session awareness.
