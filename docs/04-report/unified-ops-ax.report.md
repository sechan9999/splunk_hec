# Unified Ops AX — 완료 보고서 (Report)

- **Feature**: `unified-ops-ax`
- **완료일**: 2026-07-30
- **대상 조직**: 소규모 제조/판매업 (~50인)
- **구축 전략**: 하이브리드 (핵심 허브 자체 구축 + 회계·일정 SaaS 연동)
- **최종 상태**: PDCA 1사이클 완료 · **Match Rate 93%** · 테스트 42개 전부 통과
- **PDCA 흐름**: `[Plan] ✅ → [Design] ✅ → [Do] ✅(P1·P2·P3) → [Check] ✅88% → [Act-1] ✅93% → [Report] ✅`

---

## 1. 목표 대비 결과 (Executive Summary)

**목표**: 부서별로 흩어진 업무 흐름·데이터를 하나의 운영체계로 통합해 유기적·효율적으로 동작시킨다 (마케팅·CRM·공정·제품관리·팔로업·AS·성과·지식화·커스텀UX·회계·일정).

**달성**: 단일 `Activity` 이벤트 스트림을 진실원천(SSOT)으로 하는 **모듈러 모놀리스 백엔드**를 구축. 성과관리·회계정합·고객360°·인계자동화가 전부 이 한 스트림의 파생으로 동작함을 코드·테스트로 실증. 착수 중 추가된 **Enterprise AI Platform**(RAG·멀티LLM Gateway·SharePoint/Teams·Security Trimming·On-prem)까지 포함해 오프라인에서 즉시 실행·검증 가능한 상태로 완료.

> "완성까지"의 정직한 정의: 전사 AX는 다년 과제이므로 본 사이클의 완성물은 **P1–P3 델리버리(데이터 허브 + AI 플랫폼 + SaaS 오케스트레이션 + AI 에이전트)의 동작하는 백엔드**다. L5 경험 레이어(P4)와 거버넌스(P5)는 로드맵상 차기.

---

## 2. 산출물

### 문서 (PDCA)
| 단계 | 문서 |
|------|------|
| Plan | `docs/01-plan/features/unified-ops-ax.plan.md` |
| Design | `docs/02-design/features/unified-ops-ax.design.md` |
| Analysis | `docs/03-analysis/unified-ops-ax.analysis.md` |
| Report | `docs/04-report/unified-ops-ax.report.md` (본 문서) |

### 코드 (`unified-ops-ax/`)
- 소스 45개 파일, 테스트 42개(오프라인 통과), FastAPI 백엔드
- 실행: `pip install -r requirements.txt && pytest -q && uvicorn app.main:app`
- 키/외부서비스 없이 기본값(fake LLM·임베딩, memory 벡터, SQLite)으로 동작

---

## 3. 구현 범위 (Phase별)

### P1 — 데이터 허브 + Enterprise AI Platform
- **캐노니컬 모델**: Customer·Employee·Product·Lead·Order·OrderLine·ProductionJob·ASTicket·FollowUp·KnowledgeItem + **Activity 이벤트 스토어**
- **고객 360°** 파생 뷰 (`views/customer360.py`)
- **RAG**: 청크·임베딩·검색(인용 포함) — `rag/`
- **AI Gateway**: 멀티 LLM(fake/anthropic/openai/onprem), 단일 인터페이스 — `ai/`
- **Security Trimming**: 문서 ACL을 청크에 스냅샷 → 검색 top-k **이전** 트리밍 — `rag/vectorstore.py`, `security/`
- **SharePoint/Teams 커넥터**: Graph 인증·재귀크롤·**권한 미러(fail-closed)** + 문서 추출(txt/md/**docx(stdlib)**/**pdf(pypdf)**) — `connectors/`

### P2 — 회계·일정 SaaS 오케스트레이션
- **어댑터 패턴**: AccountingPort/CalendarPort (락인 방지) — `connectors/{accounting,calendar}.py`
- **회계**: 아웃박스 멱등 동기화 + **99% 정합 대조**(integrity_rate·missing·mismatch·orphan) — `orchestration/accounting.py`
- **일정**: 양방향 동기화(external_id upsert, last-write-wins) — `orchestration/calendar.py`

### P3 — AI 에이전트 레이어 (4종)
| 에이전트 | 역할 | 승인 |
|----------|------|------|
| AS 트리아지 | 규칙 분류 + 최소부하 배정 | 자동(가역) |
| 지식화 캡처 | 해결티켓 → KnowledgeItem draft + RAG 인덱싱(검색 루프 폐쇄) | 리뷰 큐 |
| 자동 팔로업 | 고객 맞춤 초안 | **사람 승인 발송(HITL)** |
| 성과·마케팅 인사이트 | 파생뷰 신호 감지 + 요약 | 읽기용 |
- 파생 뷰 완비: v_customer_360·v_employee_performance·v_inventory_status·v_pipeline

---

## 4. 핵심 설계 결정 & 검증

| 결정 | 근거 | 검증 |
|------|------|------|
| 단일 Activity 이벤트 스트림 = SSOT | 5개 도메인을 한 테이블이 먹임, 파생 뷰로 사일로 제거 | 360° 타임라인 E2E 6이벤트 |
| Security Trimming (top-k 이전 ACL 필터) | SharePoint식 권한 반영, 정보 유출 차단 | 영업 role이 회계문서 검색 불가 실증 |
| Fail-closed 권한 매핑 | 권한 조회 실패 시 공개 아닌 차단 | `test_permissions_failure_is_fail_closed` |
| 규칙이 라우팅 결정, LLM은 서사만 | 환각이 배정을 좌우 못함 + 오프라인 안전 폴백 | 분류 유닛테스트 |
| HITL 발송 게이트 | 외부 발송은 사람 승인 필수(안전 규칙) | 초안 후 followup.sent 없음 확인 |
| docx를 stdlib로 파싱 | 초장기 venv 경로에서 lxml DLL 로드 실패 회피 + 의존성 경감 | docx/pdf 추출 라운드트립 |
| A4 자동트리거 백로그 유지 | inline 커밋은 타 트랜잭션 중첩커밋 유발 → 실 이벤트버스(B2)와 처리가 정합 | 분석서에 근거 기록 |

---

## 5. 품질 지표

- **테스트**: 42개 전부 통과 (hub·security-trimming·gateway·rag·sharepoint·extract·accounting·calendar·agents·views/insights)
- **Match Rate**: 88%(최초) → **93%**(Act 반복1) — P1–P3 델리버리 스코프 ~97%
- **오프라인 실행성**: 외부 의존성 0로 전 경로 실행/테스트 (fake provider·MockTransport·합성 PDF/docx)
- **E2E 검증**: AS접수→트리아지→해결→지식화→검색→배송→팔로업초안→승인발송 전 여정 + 회계 정합 1.0 + 인사이트 신호 감지

---

## 6. 배운 점 (Lessons Learned)

1. **이벤트 스토어 우선 설계가 통합의 물리적 실체** — 성과·회계·360°를 파생으로 두니 도메인 추가가 값싸짐.
2. **LLM은 서사, 규칙은 결정** — 라우팅/분류를 규칙에 두어 오프라인 결정성과 프로덕션 가드레일을 동시 확보.
3. **어댑터 패턴 + Fake 구현**이 오프라인 테스트와 락인 방지를 동시에 해결.
4. **환경 제약이 더 나은 설계로** — lxml 실패가 stdlib docx 파싱(의존성 경감)으로 이어짐.
5. **수치보다 정합** — A4를 억지로 넣지 않고 아키텍처 근거와 함께 백로그화한 것이 정직한 진행.

---

## 7. 잔여 작업 (Backlog / 로드맵)

### 프로덕션 하드닝 (B)
pgvector 백엔드 · 실 이벤트버스(NOTIFY/Redis)+에이전트 자동트리거 · MCP 서버 · 인증/RBAC API 미들웨어 · Row-Level Security · PII 암호화 · 마케팅 광고 커넥터 · 재고 이동 모델 · 이메일/SMS 발송 어댑터

### 로드맵 (C)
- **P4**: L5 경험 레이어 — 역할별 워크스페이스 UX(Next.js), 개인 커스터마이즈
- **P5**: 확산·거버넌스 대시보드, 데이터 오너십, 채택 지표

### 라이브 전환
provider/크레덴셜 교체만으로 동작: `DEFAULT_LLM_PROVIDER`(anthropic/openai/onprem) · `DATABASE_URL`(Postgres) · `GRAPH_*`(SharePoint) · `ACCOUNTING/CALENDAR_PROVIDER`(SaaS)

---

## 8. 다음 단계
- `/pdca archive unified-ops-ax` — 문서 아카이브
- 또는 P4 경험 레이어 착수 (신규 PDCA 사이클)
- 또는 프로덕션 하드닝 백로그 중 우선순위 선택 (권장 순: 실 이벤트버스+자동트리거 → 인증 미들웨어 → pgvector)
