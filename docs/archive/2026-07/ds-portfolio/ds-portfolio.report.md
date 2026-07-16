# Completion Report: ds-portfolio (+ recommender v2)

- **Feature**: ds-portfolio — 4 DS 포트폴리오 모듈 + recommender 엔진 v2 개선
- **Period**: 2026-07-15 (single-day cycle)
- **Final Match Rate**: 100% (plan 수용 기준 전항목 정량 검증)
- **Status**: ✅ Completed
- **Commits**: `66ca69c` (EDA/churn/forecast), `af405a7` (sentiment + recommender v2)

---

## 1. Summary

면접용 DS 포트폴리오 모듈 4종을 `ds_portfolio/`에 구축하고, 기존 하이브리드
추천 엔진을 v2로 개선. 모든 모듈은 재현 가능한 합성 데이터 생성기 + 모델 +
평가 CLI + Streamlit 데모 페이지로 구성 (외부 다운로드 없음, 추가 의존성은
scikit-learn 하나).

**핵심 결과**:
- Churn AUC **0.811**, top-decile lift **2.6×**
- Forecast Ridge MAPE **3.4%** / WMAE **~$74k** vs seasonal-naive 5.6% / ~$122k
- Sentiment accuracy/F1/AUC **0.965** (부정어·대조절·3% 라벨 노이즈 포함)
- Recommender v2: CF NDCG@10 **0.075 → 0.120 (+60%)**, hybrid recall@10 0.186 → **0.195**

---

## 2. PDCA Cycle Trace

| Phase | Artifact | Outcome |
|-------|----------|---------|
| Plan | [ds-portfolio.plan.md](../01-plan/features/ds-portfolio.plan.md) | 3개 모듈 범위 + 성공 기준 정의 (sentiment/recommender v2는 후속 요청으로 확장) |
| Design | (skip — plan에 모듈별 설계 포함, 단일 세션 규모) | — |
| Do | `ds_portfolio/` 4 서브패키지, `pages/2~5`, recommender 3파일 수정 | 26 files, ~1,600 LOC |
| Check | 각 `run.py` 정량 평가 + 기존 테스트 회귀 (아래 §5) | 성공 기준 전항목 충족, tests 7/7 pass |
| Act | 3회 반복 (아래 §4) | forecast/sentiment/recommender 각 1회 |

> 참고: gap-detector 정식 실행 대신 plan의 성공 기준을 CLI 지표로 직접 검증함.

---

## 3. Deliverables

| Item | Path | Demo |
|------|------|------|
| EDA & 클리닝 파이프라인 (감사 로그, 비즈니스 리포트) | `ds_portfolio/eda/` | `pages/2_📊_EDA_Pipeline.py` |
| 고객 이탈 분류기 (LogReg vs GBoost, lift, 실시간 스코어링) | `ds_portfolio/churn/` | `pages/3_📞_Churn_Classifier.py` |
| 주간 매출 예측기 (Walmart 스타일, WMAE 백테스트) | `ds_portfolio/forecast/` | `pages/4_📈_Sales_Forecast.py` |
| 감성 분석기 (TF-IDF bigram + LogReg, n-gram 기여도 설명) | `ds_portfolio/sentiment/` | `pages/5_💬_Sentiment_Analyzer.py` |
| Recommender v2 (BM25 CF, rank fusion, 고속 튜닝) | `recommender/` | `pages/1_🛍️_Recommender.py` |
| 모듈 문서 | `ds_portfolio/README.md`, `recommender/README.md` §v2 | — |

### 핵심 지표

| 모듈 | 지표 | 결과 | 기준 |
|------|------|------|------|
| eda | 주입 결함 제거율 | 중복 240/240, 무효 수량 160/160 (100%) | 100% |
| churn | test AUC (logistic) | 0.811 | > 0.80 |
| forecast | Ridge vs naive WMAE | $74k vs $122k (−39%) | Ridge 우위 |
| sentiment | test acc/F1/AUC | 0.965 | (후속 확장) |
| recommender | hybrid recall@10 | 0.186 → 0.195 | 개선 |

---

## 4. Iterations (Act)

1. **Forecast — 재귀 예측 실패**: 단기 lag(1,2) 재귀 모델이 휴일 스파이크
   구간에서 오차 누적으로 baseline보다 나빴음 (WMAE 157k→242k 악화).
   원인 2가지: 단일 휴일 플래그가 규모가 다른 3개 휴일을 평균화, 피처 스케일
   불균형으로 ridge가 lag_52를 과소 사용. **직접(direct) 예측 + 휴일별 개별
   플래그 + log 변환 + StandardScaler**로 전환 → WMAE 122k → 74k.
2. **Sentiment — 템플릿 누수**: 초기 버전 정확도 100% = 라벨 전용 filler
   단어("Honestly", "Really")가 라벨을 누설. 라벨 무관 공유 오프너/필러 +
   오타 주입 + 3% 라벨 노이즈로 수정 → 현실적인 0.965.
3. **Recommender — minmax 융합 결함**: 기존 튜너가 CF 가중치를 0으로 버림.
   원인: heavy-tailed CF 점수가 minmax 정규화에서 0 근처로 뭉개짐.
   **BM25 상호작용 가중치 + rank-percentile 융합 + 컴포넌트 사전계산 튜닝
   (~6× 고속)** 적용 → CF 단독 NDCG +60%, hybrid recall +4.8%.

---

## 5. Verification

- 4개 `run.py` CLI 전부 정상 실행, 지표 위 표와 같음 (seed=42 재현 가능)
- `pytest tests -k rec`: 7/7 pass (recommender v2 회귀 없음)
- Streamlit 5개 페이지 bare-mode 실행 + 로컬 브라우저 렌더링 확인
- Streamlit Cloud 배포: master push로 자동 배포 (`requirements.txt`에
  scikit-learn 추가)

## 6. Lessons

- **합성 데이터는 어렵게 만들어야 증명력이 있다**: 완벽 분류(100%)는 데이터
  결함 신호. 공유 어휘·노이즈 주입 후의 0.96대가 오히려 신뢰할 수 있는 결과.
- **다단계 예측은 재귀보다 직접**: 예측 시점에 알려진 피처(lag-52, 달력,
  계획된 이벤트)만으로 구성하면 오차 누적이 원천 차단됨.
- **점수 융합은 정규화가 절반**: 분포가 다른 신호를 섞을 때 minmax는
  위험하고 rank-percentile이 견고함.

## 7. Follow-ups (optional)

- churn: 캘리브레이션 곡선 + 비용 기반 threshold 최적화
- forecast: 매장×부서 계층 예측, prediction interval
- recommender: 유사도 레벨 CF+content 블렌딩 실험 (현재는 점수 레벨)
- `/pdca archive ds-portfolio --summary`로 아카이브
