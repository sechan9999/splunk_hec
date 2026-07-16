# Archive Index: 2026-07

| Feature | Archived | Match Rate | Iterations | Documents |
|---------|----------|-----------:|-----------:|-----------|
| recommender-system | 2026-07-14 | 95% | 2 | [plan](recommender-system/recommender-system.plan.md) · [design](recommender-system/recommender-system.design.md) · [analysis](recommender-system/recommender-system.analysis.md) · [report](recommender-system/recommender-system.report.md) |
| ds-portfolio | 2026-07-15 | 100% | 3 | [plan](ds-portfolio/ds-portfolio.plan.md) · [report](ds-portfolio/ds-portfolio.report.md) |

## recommender-system

하이브리드 추천 시스템 (user behavior + product data + context signals).
단일 세션 PDCA 사이클 완료 — hybrid NDCG@10 0.114 vs popularity 0.058.
구현: `recommender/` 패키지 (master `56d3fca`), 데모: `recommender/demo/hybrid-recommender-demo.html`.

## ds-portfolio

DS 포트폴리오 모듈 4종 (EDA 클리닝 파이프라인, churn 분류기, 주간 매출 예측기,
감성 분석기) + recommender v2 개선 (BM25 CF, rank fusion).
핵심 지표: churn AUC 0.811 · forecast WMAE −39% vs naive · sentiment 0.965 ·
hybrid recall@10 0.186→0.195. Act 반복 3회 (재귀 예측 실패, 템플릿 누수,
minmax 융합 결함 — 상세는 report §4).
구현: `ds_portfolio/` + `pages/2~5` (master `66ca69c`, `af405a7`), design/analysis 문서 없음
(plan 성공 기준을 CLI 지표로 직접 검증).
