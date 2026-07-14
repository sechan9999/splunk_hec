# Plan: recommender-system

## Overview
고객 경험 개선을 위한 하이브리드 추천 시스템.
사용자 행동(implicit feedback), 상품 메타데이터, 컨텍스트 신호(시간대, 디바이스)를 결합한
모델 개발 + 오프라인 평가 하네스 + 프로덕션 배포용 서빙 API까지 end-to-end 구현.

- **Status**: Plan
- **Created**: 2026-07-14
- **Priority**: P0
- **Deliverable**: `recommender/` Python 패키지 + FastAPI 서빙 + 평가 리포트

---

## Goals

1. 사용자 행동·상품·컨텍스트를 결합하는 하이브리드 추천 모델 개발
2. 베이스라인(popularity, item-item CF, content-based) 대비 성능 검증
3. 오프라인 평가 하네스 (temporal split, Recall@K, NDCG@K, coverage)
4. 엔지니어링 인계 가능한 서빙 API (FastAPI) + 프로덕션 반복 개선 가이드

---

## Scope

### In Scope
- `recommender/data.py` — e-commerce 스타일 합성 이벤트 생성기 (view/click/cart/purchase + 컨텍스트)
- `recommender/models/` — popularity, item-item CF, content-based, hybrid contextual ranker
- `recommender/evaluate.py` — temporal split, Recall@K / NDCG@K / catalog coverage
- `recommender/service.py` — FastAPI `/recommend` 엔드포인트 (cold-start fallback 포함)
- `recommender/run_eval.py` — 전체 모델 학습 + 비교 테이블 출력
- `tests/` — 핵심 로직 단위 테스트
- `README.md` — 아키텍처, 실행법, 프로덕션 배포/반복 전략

### Out of Scope
- 실제 사용자 데이터 수집 파이프라인 (합성 데이터로 대체)
- 딥러닝 모델 (two-tower, sequence) — 반복 개선 로드맵에만 기재
- 온라인 A/B 테스트 인프라 — 설계 문서에 계획만 기술

---

## Acceptance Criteria

- [ ] `python -m recommender.run_eval` 실행 시 4개 모델 비교 테이블 출력
- [ ] Hybrid 모델이 popularity 베이스라인 대비 NDCG@10 상회
- [ ] Temporal split 기반 평가 (leakage 없음)
- [ ] Cold-start 사용자에 대해 graceful fallback (popularity)
- [ ] FastAPI 서비스가 user_id + context를 받아 top-K 추천 반환
- [ ] 단위 테스트 통과

---

## Implementation Order

1. **데이터 생성기** — 세그먼트 기반 사용자, 카테고리 기반 상품, 컨텍스트 있는 이벤트 로그
2. **베이스라인 모델** — popularity(시간 감쇠), item-item CF, content-based
3. **하이브리드 모델** — CF + content + context affinity 결합 랭커
4. **평가 하네스** — temporal split, Recall@K/NDCG@K/coverage, 비교 테이블
5. **서빙 API** — FastAPI, cold-start fallback, latency 로깅
6. **테스트 + README** — 검증 후 문서화
