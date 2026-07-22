# Archive Index: 2026-07

| Feature | Archived | Match Rate | Iterations | Documents |
|---------|----------|-----------:|-----------:|-----------|
| recommender-system | 2026-07-14 | 95% | 2 | [plan](recommender-system/recommender-system.plan.md) · [design](recommender-system/recommender-system.design.md) · [analysis](recommender-system/recommender-system.analysis.md) · [report](recommender-system/recommender-system.report.md) |
| ds-portfolio | 2026-07-15 | 100% | 3 | [plan](ds-portfolio/ds-portfolio.plan.md) · [report](ds-portfolio/ds-portfolio.report.md) |
| datahub-eval-loop | 2026-07-22 | 96% | 1 | [plan](datahub-eval-loop/datahub-eval-loop.plan.md) · [analysis](datahub-eval-loop/datahub-eval-loop.analysis.md) · [report](datahub-eval-loop/datahub-eval-loop.report.md) |

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

## datahub-eval-loop

DataHub 가드레일을 평가·회귀 루프로 감싼 사이클. 정책을 코드에서 꺼내 버전 관리되는
계약(`policies/governance.yaml`, CODEOWNERS 리뷰)으로 만들고, 잘못된 판정을 영구
골든 케이스로 고정, 커버리지 게이트로 규칙 추가 시 테스트 누락을 차단, 차단을
후속 데이터셋 리다이렉트로 전환.
Check 83% → Act 1회 → 96%. 테스트 10 → 72개, 정책 평가 지연 p95 0.014ms.

**루프가 만들어지는 도중 잡은 결함 4건** — 통과 중이던 유닛 테스트 10개가 못 본 것들:
마스킹된 catastrophic 판정, 감사 흔적을 남기지 않던 HIPAA 접근, 엔진이 내지 않는
판정을 보여주던 데모, UI가 아직 렌더링하지 않던 제출 문안의 주장.
구현: `sechan9999/splunk_hec_v2` (`60cac0a`, `2e87ccf`, `451c170`, `5229215`,
PR #1 `5a84157`). 착안: Slack 데이터 에이전트 운영 사례 기사와의 갭 분석
(개념만 차용, 수치는 전부 자체 측정).
