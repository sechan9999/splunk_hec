# Gap Analysis: recommender-system

- **Design**: [recommender-system.design.md](../02-design/features/recommender-system.design.md)
- **Analyzed**: 2026-07-14
- **Match Rate**: 95%

## Acceptance Criteria Check

| Criterion | Status | Evidence |
|-----------|--------|----------|
| `python -m recommender.run_eval` 비교 테이블 | ✅ | 4개 모델 테이블 출력 확인 |
| Hybrid > popularity NDCG@10 | ✅ | 0.1137 vs 0.0581 (+96%) |
| Temporal split, leakage 없음 | ✅ | day 0–70/70–80/80–90, `test_ground_truth_excludes_seen` 통과 |
| Cold-start fallback | ✅ | `test_cold_start_fallback` + API `cold_start: true` 확인 |
| FastAPI top-K + context | ✅ | TestClient 스모크 테스트, reason 필드 포함 |
| 단위 테스트 통과 | ✅ | 7/7 passed |

## Design vs Implementation Deltas

1. **초기 데이터 파라미터 수정** (설계 반영됨): Pareto(1.5) 인기도 skew가 너무 강해
   튜너가 pure popularity로 붕괴 → lognormal(0, 0.6)로 완화, 세그먼트 affinity 강화.
   합성 데이터 실험에서 흔한 함정 — 실데이터 적용 시 재검토 필요.
2. **가중치 grid**: 설계는 3-way grid + 고정 w_pop이었으나 4-way full grid로 확장
   (dedup 포함, val 튜닝 ~28s).
3. **미구현 (Out of Scope 유지)**: A/B 인프라, 딥러닝 모델 — README 로드맵에 기재.

## Conclusion

Match Rate ≥ 90% → `/pdca report recommender-system` 진행 가능.
