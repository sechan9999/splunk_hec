"""FastAPI serving layer.

Demo mode fits on synthetic data at startup. In production, replace with
artifact loading (batch-trained model) — the request path stays identical.

Run: uvicorn recommender.service:app --port 8100
"""
from __future__ import annotations

import time

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .data import generate
from .models import HybridContextualRecommender
from .models.base import Context

app = FastAPI(title="Hybrid Recommender", version="0.1.0")
_model: HybridContextualRecommender | None = None
_item_meta: dict[int, dict] = {}


class RecommendRequest(BaseModel):
    user_id: int
    device: str = Field("mobile", pattern="^(mobile|desktop)$")
    hour_bucket: str = Field("evening", pattern="^(morning|day|evening|night)$")
    is_weekend: bool = False
    k: int = Field(10, ge=1, le=50)


class RecommendedItem(BaseModel):
    item_id: int
    score: float
    category: str
    reason: dict


class RecommendResponse(BaseModel):
    items: list[RecommendedItem]
    model: str
    cold_start: bool
    latency_ms: float


@app.on_event("startup")
def _startup() -> None:
    global _model, _item_meta
    users, items, events = generate()
    _model = HybridContextualRecommender().fit(events, items)
    _item_meta = items.set_index("item_id")[["category", "price_tier"]].to_dict("index")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": _model.name if _model else None}


@app.post("/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest) -> RecommendResponse:
    t0 = time.perf_counter()
    ctx = Context(req.device, req.hour_bucket, req.is_weekend)
    cold = req.user_id not in _model.seen
    recs = _model.recommend(req.user_id, ctx, k=req.k)
    items = [
        RecommendedItem(
            item_id=i,
            score=round(s, 4),
            category=_item_meta.get(i, {}).get("category", "unknown"),
            reason={} if cold else _model.explain(req.user_id, i, ctx),
        )
        for i, s in recs
    ]
    return RecommendResponse(
        items=items,
        model=_model.name,
        cold_start=cold,
        latency_ms=round((time.perf_counter() - t0) * 1000, 2),
    )
