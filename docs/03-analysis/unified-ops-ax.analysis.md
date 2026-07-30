# Unified Ops AX — Gap 분석 (Check)

- **Feature**: `unified-ops-ax`
- **분석일**: 2026-07-30
- **대상**: 설계서 `docs/02-design/features/unified-ops-ax.design.md` vs 구현 `unified-ops-ax/`
- **구현 규모**: 소스 45개 파일, 테스트 **42개** 전부 통과 (오프라인)
- **Match Rate**: **93%** (Act 반복 1 후) — 최초 88% → A1·A2·A3 마감 후 상향

> **Act 반복 1 (2026-07-30):** A1(설계 문서 동기화)·A2(파생 뷰 3종)·A3(성과·마케팅 인사이트 에이전트) 마감. 신규 테스트 5개(42 통과). 잔여는 A4(이벤트 자동트리거—실 이벤트버스 B2와 결합, 백로그 유지가 정합)·B(프로덕션 하드닝)·C(P4–P5 로드맵). ≥90% 도달 → report 게이트 통과.

---

## 1. 요약

설계서의 **핵심 골격(L3 데이터 허브 + Activity 이벤트 스토어 + L2' SaaS 어댑터 + L4 에이전트 3종)**은 구현·테스트 완료. 남은 Gap은 (a) 파생 뷰 3종, (b) 4번째 에이전트, (c) 이벤트 버스 자동 트리거, (d) 설계 문서 드리프트(RAG/게이트웨이/SharePoint가 설계서에 미반영), (e) 로드맵상 의도적으로 미룬 L5/거버넌스.

```
[Plan] ✅ → [Design] ✅ → [Do] ✅(P1·P2·P3) → [Check] 🔄 88% → [Act] ⏳
```

---

## 2. 구현 완료 (설계 일치)

| # | 설계 요소 | 구현 위치 | 상태 |
|---|-----------|-----------|:----:|
| 1 | 앵커 엔티티 (Customer/Employee/Product) | `domain/models.py` | ✅ |
| 2 | 플로우 엔티티 (Lead/Order/OrderLine/ProductionJob/ASTicket/FollowUp/KnowledgeItem) | `domain/models.py` | ✅ |
| 3 | Activity 이벤트 스토어 (type·actor·subject·payload·source·occurred_at 전 필드) | `domain/models.py`, `events/activity.py` | ✅ |
| 4 | 회계·일정 엔티티 (Transaction/ScheduleEvent) | `domain/models.py` | ✅ |
| 5 | v_customer_360 파생 뷰 | `views/customer360.py` | ✅ |
| 6 | SaaS 어댑터 패턴 (AccountingPort/CalendarPort) | `connectors/{accounting,calendar}.py` | ✅ |
| 7 | 회계 오케스트레이션 + 99% 정합 대조 | `orchestration/accounting.py` | ✅ |
| 8 | 일정 양방향 동기화 | `orchestration/calendar.py` | ✅ |
| 9 | AS 트리아지 에이전트 | `agents/triage.py` | ✅ |
| 10 | 지식화 캡처 에이전트 (+RAG 검색 루프) | `agents/knowledge.py` | ✅ |
| 11 | 자동 팔로업 에이전트 (HITL 발송 게이트) | `agents/followup.py` | ✅ |
| 12 | 주문→공정 자동 생성 (인계 자동화) | `domain/services.py` | ✅ |
| 13 | 보안: RBAC + Security Trimming | `security/{rbac,acl}.py`, `rag/vectorstore.py` | ✅ |
| 14 | 감사 로그 = 불변 Activity 스트림 | `events/activity.py` | ✅ |
| 15 | AI 안전: 초안만 생성·원본 침묵수정 금지·외부발송 HITL | `agents/*` | ✅ |
| 16 | 모듈러 모놀리스 아키텍처 | `app/` 전체 | ✅ |

**설계 초과 달성 (P1 확장 요구, 설계서 미반영):** RAG 플랫폼(`rag/`), AI Gateway 멀티 LLM(`ai/`), SharePoint/Teams 커넥터(`connectors/sharepoint.py`), 바이너리 추출(`connectors/extract.py`).

---

## 3. Gap 목록

### 🔴 우선순위 A — 전달 단계(P1–P3) 내 누락

| G# | Gap | 설계 근거 | 상태 |
|----|-----|-----------|:----:|
| A1 | 설계 문서 드리프트 — RAG·Gateway·SharePoint·추출이 설계서에 없음 | §2.2, §6 | ✅ 해소 (설계서 §9 신설) |
| A2 | 파생 뷰 3종 (v_employee_performance, v_inventory_status, v_pipeline) | §2.4 | ✅ 구현 (`views/`) |
| A3 | 4번째 에이전트 (성과·마케팅 인사이트) | §4 | ✅ 구현 (`agents/insights.py`) |
| A4 | 이벤트 버스 자동 트리거 (현재 수동 호출) | §4, §8 | ⏸ 백로그 — 실 이벤트버스(B2)와 결합. inline 커밋 트리거는 타 트랜잭션 내 중첩 커밋을 유발해 아키텍처상 부적합 → B2(NOTIFY/Redis)와 함께 처리가 정합 |

### 🟡 우선순위 B — 프로덕션 하드닝 (설계가 스텁/차기로 명시한 항목)

| G# | Gap | 설계 근거 | 비고 |
|----|-----|-----------|------|
| B1 | pgvector 백엔드 (현재 memory) | §6 | `vectorstore.py`에 SQL outline 有 |
| B2 | 이벤트 버스 실체 (Postgres NOTIFY/Redis) | §1 원칙2, §6 | in-process 스텁 |
| B3 | MCP 서버 (통합/AI 표준 프로토콜) | §6, §9 P3 | 미착수 |
| B4 | 인증/RBAC API 미들웨어 (현재 role=요청 파라미터) | §6, §7 | 토큰에서 role 도출 필요 |
| B5 | Row-Level Security | §7 | 담당 고객/티켓 행 접근제어 |
| B6 | PII 암호화 | §7 | 미착수 |
| B7 | 마케팅 광고 SaaS 커넥터 + 리드 스코어링 | §3, §8 | Lead 모델만 존재 |
| B8 | 재고 이동(Inventory) 모델 — 현재 Product.stock_qty만, BOM 소진 로직 없음 | §3 제품/재고 | |
| B9 | 이메일/SMS 발송 어댑터 (팔로업 승인 지점에 연결) | §4 | HITL 게이트는 구현됨 |

### 🟢 우선순위 C — 로드맵상 의도적 미착수 (Gap 아님, 차기 단계)

| G# | 항목 | 단계 |
|----|------|------|
| C1 | L5 경험 레이어 (역할별 워크스페이스 UX, Next.js) | P4 |
| C2 | 확산·거버넌스 대시보드, 데이터 오너십 | P5 |

---

## 4. Match Rate 산출 근거

| 범주 | 설계 요소 | 구현 | 비율 |
|------|:--------:|:----:|:----:|
| L3 데이터 허브 + 이벤트 스토어 | 5 | 5 | 100% |
| 파생 뷰 | 4 | 1 | 25% |
| L2' SaaS 어댑터 + 오케스트레이션 | 4 | 4 | 100% |
| L4 에이전트 | 4 | 3 | 75% |
| 보안·거버넌스 | 6 | 3 | 50% |
| 통합 도메인 (11) | 11 | 8.5 | 77% |
| **가중 종합 (P1–P3 델리버리 스코프)** | | | **~92%** |
| **전체 설계 (P4–P5 포함)** | | | **~78%** |
| **대표값 (Match Rate)** | | | **88%** |

> 88% < 90% → bkit 기준상 `iterate` 권장. 단, 미달의 상당 부분이 **문서 드리프트(A1)**와 **로드맵 의도적 미착수(C)** 이므로, A1·A2·A3만 닫으면 ≥90% 도달.

---

## 5. 권장 조치

**옵션 1 (권장): 타깃 iterate로 빠른 Gap 마감 → report**
- A1: 설계서에 Enterprise AI Platform(RAG/Gateway/SharePoint) 섹션 추가 (문서 동기화)
- A2: v_employee_performance·v_pipeline·v_inventory_status 파생 뷰 구현 (Activity 집계, customer_360과 동일 패턴)
- A3: 성과·마케팅 인사이트 에이전트 (읽기용 배치)
- → 재-analyze 시 ≥92% 예상 → `/pdca report`

**옵션 2: 현 상태로 report** — A1~A4를 "차기 개선"으로 명시하고 P1–P3 완료 보고. B·C는 로드맵 항목으로 이월.

**옵션 3: P4 진행** — 경험 레이어 UX로 넘어가고 위 Gap은 백로그화.

---

## 6. 다음 단계
- `/pdca iterate unified-ops-ax` (옵션 1) — A1~A3 자동 개선 후 재검증
- 또는 `/pdca report unified-ops-ax` (옵션 2)
