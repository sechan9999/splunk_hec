# Design: recommender-system

- **Plan**: [recommender-system.plan.md](../../01-plan/features/recommender-system.plan.md)
- **Created**: 2026-07-14
- **Dependencies**: numpy, pandas, fastapi (sklearn 불필요 — numpy로 직접 구현)

---

## 1. Architecture

```
recommender/
├── __init__.py
├── data.py            # 합성 이벤트 생성기 (users, items, events + context)
├── models/
│   ├── __init__.py
│   ├── base.py        # BaseRecommender 인터페이스
│   ├── popularity.py  # 시간 감쇠 인기도 (베이스라인 + cold-start fallback)
│   ├── item_cf.py     # Item-item cosine CF (implicit weights, shrinkage)
│   ├── content.py     # Content-based (item features × user profile)
│   └── hybrid.py      # Hybrid: CF + content + popularity + context affinity
├── evaluate.py        # Temporal split, Recall@K, NDCG@K, coverage
├── run_eval.py        # python -m recommender.run_eval → 비교 테이블
└── service.py         # FastAPI /recommend, /health
tests/
└── test_recommender.py
```

## 2. Data Model (synthetic, e-commerce)

| Entity | Fields |
|--------|--------|
| users (1,200) | user_id, segment (tech/fashion/sports/home/budget) |
| items (300) | item_id, category (8종), price_tier (1–3), base_popularity |
| events (~100K, 90일) | user_id, item_id, event_type, ts, device, hour_bucket, is_weekend |

- Implicit weight: view=1.0, click=2.0, add_to_cart=3.0, purchase=5.0
- 생성기에 실제 신호 주입: 세그먼트→카테고리 선호, 컨텍스트→카테고리 부스트
  (예: mobile+evening → fashion/sports 상승) → 컨텍스트 모델이 학습할 신호 보장

## 3. Models

모든 모델은 `BaseRecommender.fit(events, items)` / `recommend(user_id, context, k, exclude_seen)` 구현.
점수는 블렌딩 전 min-max 정규화.

1. **Popularity**: `Σ weight × exp(-λ·age_days)`, λ=0.03
2. **ItemItemCF**: user-item implicit matrix → item-item cosine + shrinkage(β=25).
   `score(u,i) = Σ_j sim(i,j) × w(u,j) × recency(u,j)`
3. **ContentBased**: item vector = [category one-hot, price_tier scaled].
   user profile = 상호작용 가중 평균 → cosine similarity
4. **HybridContextual**:
   `score = w_cf·CF + w_ct·Content + w_pop·Pop + w_ctx·ContextAffinity`
   - ContextAffinity: train에서 P(category | device, hour_bucket, weekend) 카운트 기반
   - 가중치는 validation(temporal) NDCG@10 grid search로 자동 튜닝
   - Cold-start(이력 없음): Pop + ContextAffinity만 사용

## 4. Evaluation

- **Temporal split**: day 0–70 train / 70–80 validation(가중치 튜닝) / 80–90 test
- Test positives: click 이상 이벤트 중 train에 없는 아이템 (leakage 방지)
- Metrics: Recall@10, NDCG@10, catalog coverage@10
- 산출: 모델별 비교 테이블 (stdout + `docs/03-analysis/` 리포트에 반영)

## 5. Serving API

- `GET /health`
- `POST /recommend` → `{user_id, device, hour, k}` → `{items: [{item_id, score, reason}], model, latency_ms, cold_start}`
- Startup 시 fit (데모용). 프로덕션 전환: 배치 학습 → artifact 저장 → 서빙은 load만
- `reason` 필드로 추천 근거 노출 (CF/content/context 기여)

## 6. Production Iteration Plan (엔지니어링 협업)

1. 로깅: impression/click 피드백 루프 → 재학습 배치 (daily)
2. 실험: 인터리빙 또는 A/B, 가드레일 = CTR, coverage, latency p99 < 50ms
3. 확장 로드맵: ALS/BPR → two-tower retrieval + LightGBM ranker → sequence 모델
