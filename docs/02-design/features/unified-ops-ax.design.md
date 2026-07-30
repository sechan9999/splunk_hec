# Unified Ops AX — 아키텍처 설계서 (Design)

- **Feature**: `unified-ops-ax`
- **작성일**: 2026-07-30
- **연계 기획서**: [unified-ops-ax.plan.md](../../01-plan/features/unified-ops-ax.plan.md)
- **아키텍처 스타일**: 모듈러 모놀리스 + 이벤트 버스 + AI 에이전트 레이어 (50인 규모 최적)

---

## 1. 시스템 개요 — 5-레이어 아키텍처

핵심 사상: **하나의 이벤트 스트림 위에 모든 부서가 앉는다.** 성과·회계·지식은 별도 시스템이 아니라 이 스트림의 *파생 뷰*.

```
┌──────────────────────────────────────────────────────────────────────┐
│  L5  경험 레이어 (Experience)  — "같은 데이터, 다른 창"                 │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐            │
│  │ 영업/CRM  │ 공정작업자 │ AS/CS    │ 회계담당  │ 경영/관리 │  역할별   │
│  │ 워크스페이스│ 워크스페이스│ 워크스페이스│ 워크스페이스│ 대시보드  │  커스텀UX │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘            │
└───────────────────────────────▲──────────────────────────────────────┘
                                 │ role-scoped API / RBAC
┌───────────────────────────────┴──────────────────────────────────────┐
│  L4  AI 에이전트 레이어 (Intelligence)  — AX 차별 지점                  │
│  ┌────────────┬────────────┬────────────┬────────────┐               │
│  │ 지식화 캡처 │ 자동 팔로업 │ AS 트리아지 │ 성과·마케팅 │  Claude 기반  │
│  │ 에이전트    │ 에이전트    │ 에이전트    │ 인사이트    │  (HITL 승인)  │
│  └────────────┴────────────┴────────────┴────────────┘               │
└───────────────────────────────▲──────────────────────────────────────┘
                                 │ subscribe events / write drafts
┌───────────────────────────────┴──────────────────────────────────────┐
│  L3  데이터 허브 (SSOT)  — 자체 구축, 심장부                            │
│   Canonical Data Model  ─────  Event Store (Activity stream)          │
│   PostgreSQL  │  파생 뷰(성과/회계미러/재고)  │  전문검색(지식)          │
└──────▲─────────────────────────────────────────────────▲─────────────┘
       │ ingest/normalize                       sync ↕    │
┌──────┴───────────────────┐            ┌─────────────────┴─────────────┐
│ L2 통합 레이어(Integration)│            │ L2' SaaS 커넥터(어댑터 패턴)   │
│  이벤트 버스 · 정규화 워커  │            │  회계SaaS · 캘린더 · 광고플랫폼 │
│  (자체 도메인 write API)   │            │  (MCP / REST, 양방향 동기화)   │
└───────────────────────────┘            └───────────────────────────────┘
```

---

## 2. 캐노니컬 데이터 모델 (SSOT)

### 2.1 축(Anchor) 엔티티 — 모든 것이 여기에 매달린다

- **Customer** — 고객 360°의 중심
- **Employee** — 성과·활동의 주체
- **Product (SKU)** — 제조/판매의 대상

### 2.2 핵심 엔티티 & 관계

```
Customer ──1:N── Lead ──(전환)──▶ Order ──1:N── OrderLine ──N:1── Product
   │                                  │                              │
   │                                  ├──1:1── ProductionJob         ├──1:N── BOM
   │                                  │          (제작 공정)          │
   │                                  ├──1:N── Delivery              └── Inventory(재고 이동)
   │                                  │
   ├──1:N── ASTicket (사후 서비스)     └──1:N── Transaction(회계, SaaS 미러)
   │
   └──1:N── FollowUp (후속 팔로업)

Employee ──1:N── Activity ──N:1── (Customer│Order│ProductionJob│ASTicket)
                    │
                    └──▶ KnowledgeItem (활동에서 파생된 지식)

PerformanceMetric ◀── (Activity 스트림 집계, 파생 뷰)
ScheduleEvent ◀──▶ 캘린더 SaaS (양방향)
```

### 2.3 원자 단위: `Activity` (이벤트 스토어의 핵)

모든 부서 행위는 Activity 한 줄로 기록된다. 이것이 "유기적 연결"의 물리적 실체.

| 필드 | 설명 |
|------|------|
| `id` | 이벤트 ID |
| `type` | `lead.created` / `order.placed` / `production.step_done` / `as.opened` / `followup.sent` ... |
| `actor_employee_id` | 행위 주체 (성과 귀속) |
| `subject_type` / `subject_id` | 앵커 (customer/order/product/asticket) |
| `payload` | 도메인별 상세 (JSONB) |
| `occurred_at` | 발생 시각 |
| `source` | `app` / `accounting_saas` / `calendar` / `agent` |

> **왜 이 구조인가**: 성과관리 = Activity를 employee로 group by. 고객 360° = Activity를 customer로 필터. 회계 정합성 = `order.placed` ↔ SaaS `transaction` 매칭. 인계 자동화 = Activity 발생 시 이벤트 버스가 다음 담당자에게 전파. **한 테이블이 5개 도메인을 먹인다.**

### 2.4 파생 뷰 (별도 저장 아님, 실시간 계산)

- `v_customer_360`: 고객별 리드·주문·공정·납품·AS·팔로업 타임라인
- `v_employee_performance`: 직원별 활동량·전환율·응답시간·품질지표
- `v_inventory_status`: OrderLine + ProductionJob + BOM 소진 실시간 재고
- `v_pipeline`: 마케팅 리드 → 매출 퍼널

---

## 3. 도메인별 통합 설계 (Build vs Connect)

| 도메인 | 구현 | 데이터 흐름 |
|--------|------|-----------|
| 마케팅 | 자체 `Lead` + 광고 SaaS 커넥터 | 광고플랫폼 → 리드 유입 이벤트 정규화 → Lead 생성 |
| CRM/영업 | 자체 `Customer`/`Lead`/`Order` | 앱 직접 write, 고객 360° 소유 |
| 제작 공정 | 자체 `ProductionJob`/`WorkStep` | 주문 확정 → Job 자동 생성 → 단계별 `production.*` 이벤트 |
| 제품/재고 | 자체 `Product`/`BOM`/`Inventory` | 공정 소진·입고 이벤트 → 재고 뷰 실시간 |
| 후속 팔로업 | 자체 + **에이전트** | 납품/AS 종료 이벤트 → 팔로업 에이전트가 초안 → 사람 승인 |
| AS | 자체 `ASTicket` + **에이전트** | 접수 → 트리아지 에이전트 분류·담당배정 초안 |
| 성과관리 | 파생 뷰 (무구현 저장) | Activity 집계, 실시간 |
| 지식화 | 자체 `KnowledgeItem` + **에이전트** | Activity/문서 → 캡처 에이전트가 구조화·태깅 |
| 커스텀 UX | 경험 레이어 (L5) | role + user preference 로 뷰 조립 |
| 회계 | **SaaS 연동** (어댑터) | `order.placed`/`delivery.done` → SaaS 전표, SaaS 결과 → `Transaction` 미러 |
| 일정 | **SaaS 연동** (양방향) | `ScheduleEvent` ↔ Google/MS Calendar sync |

### 3.1 SaaS 커넥터 — 어댑터 패턴 (락인 방지)

```
core → AccountingPort(interface) ← DouzoneAdapter / QuickBooksAdapter
core → CalendarPort(interface)   ← GoogleCalAdapter / MSGraphAdapter
```
core는 포트만 안다. SaaS 교체 = 어댑터 교체. 원본 이벤트는 항상 자체 허브 보유.

---

## 4. AI 에이전트 레이어 (L4) — AX의 핵심

각 에이전트는 이벤트를 구독 → Claude 호출 → **초안(draft)** 생성 → 중요 액션은 사람 승인(HITL).

| 에이전트 | 트리거 이벤트 | 산출 | 승인 |
|----------|-------------|------|------|
| 지식화 캡처 | `as.resolved`, `production.issue`, 회의노트 | 구조화된 KnowledgeItem(문제·원인·해결·태그) | 자동(리뷰 큐) |
| 자동 팔로업 | `delivery.done`, `followup.due` | 고객 맞춤 팔로업 메시지 초안 | 담당자 승인 후 발송 |
| AS 트리아지 | `as.opened` | 카테고리·심각도·담당자 추천 | 자동 배정 + override |
| 성과·마케팅 인사이트 | 일/주 배치 | 이상징후·기회 요약, 퍼널 병목 | 읽기용 |

> **원칙**: 에이전트는 절대 원본 데이터를 침묵 수정하지 않는다. 항상 `source=agent`로 이벤트를 남기고, 외부 발송·자금·계약 액션은 사람 승인 필수(안전 규칙 준수).

### 4.1 지식화 자동 캡처 시퀀스 (예시)

```
1. AS 담당자가 티켓 해결 → Activity(as.resolved, payload=처리내역)
2. 이벤트 버스 → 지식화 에이전트 트리거
3. 에이전트: Claude로 "증상/원인/조치/재발방지/태그" 구조화
4. KnowledgeItem(draft) 생성 → 리뷰 큐
5. 유사 티켓 발생 시 트리아지 에이전트가 이 지식 검색·제안
   → 암묵지가 조직 자산으로 축적 (지식 휘발 P4 해결)
```

---

## 5. 경험 레이어 (L5) — 개인별 커스텀 UX

같은 SSOT, 역할·개인별로 다른 창. 정착률(채택)의 핵심.

- **역할 프리셋**: 영업/공정작업자/AS/회계/경영 별 기본 워크스페이스(위젯 세트).
- **개인 커스터마이즈**: 위젯 추가/제거/배치, 알림 임계값, 즐겨찾기 필터를 user preference로 저장.
- **위젯 = 파생 뷰 바인딩**: 예) 영업은 `v_pipeline`+`v_customer_360`, 공정은 오늘의 WorkStep 큐, 경영은 `v_employee_performance`+매출.
- **동일 데이터 원칙**: 위젯은 표현일 뿐, 권한(RBAC) 내에서 같은 허브를 조회. 사일로 재생성 금지.

---

## 6. 기술 스택 (50인 규모 최적, 운영부담 최소)

| 레이어 | 선택 | 이유 |
|--------|------|------|
| 데이터 허브 | **PostgreSQL** (Supabase 관리형 권장) | JSONB 이벤트+관계형 뷰, 관리형으로 운영 인력 절감 |
| 이벤트 버스 | Postgres LISTEN/NOTIFY 또는 경량 큐(Redis) | 소규모엔 별도 Kafka 과잉 |
| 백엔드 | **모듈러 모놀리스** (Node/TS 또는 Python) | 도메인별 모듈 분리, MSA 오버헤드 회피 |
| 통합/워커 | 커넥터 워커 + **MCP 서버** | AI·외부 SaaS 표준 연동 프로토콜 |
| AI | **Claude API** (claude-opus / sonnet) | 에이전트 추론, HITL 파이프라인 |
| 프런트 | **Next.js** + 위젯 프레임 | 역할별 워크스페이스 조립 |
| 인증/RBAC | 관리형 Auth (Supabase Auth 등) | 역할·행별 접근제어 |

> 규모 성장 시(→500인) 모듈 → 서비스 분리, 이벤트 버스 → Kafka로 승격 가능한 진화 경로 확보.

---

## 7. 보안 & 거버넌스

- **RBAC**: 역할별 도메인·필드 접근제어. 회계·성과 데이터는 최소권한.
- **Row-Level Security**: 담당 고객/티켓만 조회(관리자 예외).
- **감사 로그**: Activity 스트림 자체가 불변 감사 추적(누가·언제·무엇).
- **데이터 소유권**: 도메인별 데이터 오너 지정(P0 거버넌스).
- **AI 안전**: 에이전트 외부 액션(발송/자금/계약)은 사람 승인 필수, 자동 실행 금지.
- **PII**: 고객 개인정보 암호화·접근 최소화, SaaS 전송 시 최소 필드.

---

## 8. 대표 엔드투엔드 시퀀스 — "리드 하나가 전 부서를 흐른다"

```
마케팅  광고클릭 → Lead 생성           [Activity lead.created]
  ↓ (에이전트: 리드 스코어링 초안)
영업    상담 → 전환 → Order 확정        [order.placed] → 회계SaaS 전표 자동
  ↓ (이벤트 전파, 수작업 인계 제거)
공정    ProductionJob 자동 생성 → 단계별 [production.step_done] → 재고 뷰 갱신
  ↓
물류    Delivery 완료                   [delivery.done]
  ↓ (팔로업 에이전트 트리거)
CS      팔로업 메시지 초안 → 담당 승인·발송 [followup.sent]
  ↓ (문제 시)
AS      티켓 접수 → 트리아지 에이전트 분류  [as.opened→resolved]
  ↓ (지식화 에이전트)
지식    KnowledgeItem 자동 축적
전 과정  → v_employee_performance / v_customer_360 실시간 반영
```
한 고객의 여정이 **끊김 없이 한 스트림**으로 흐르고, 성과·회계·지식이 자동 파생됨 = 기획서 P1~P6 통증 동시 해소.

---

## 9. Enterprise AI Platform (P1 확장 — 구현 반영)

착수 시 "사내 문서 이해 RAG · 멀티 LLM Gateway · Teams/SharePoint 연계 · Security Trimming · On-prem 확장" 요구가 추가되어 L3/L4에 다음이 구현되었다. (구현: `unified-ops-ax/app/`)

```
문서 소스(SharePoint/Teams/로컬)                    멀티 LLM
   │ Graph 인증·크롤·권한미러(ACL)                    │ fake/anthropic/openai/onprem
   ▼                                                  ▼
Document/DocumentChunk ──embed──▶ VectorStore ──검색(Security Trimming: ACL∩principals)──▶ RAG
   (connectors/)          (ai/embeddings)  (rag/vectorstore) │                        (rag/service)
                                                              ▼
                                                        AI Gateway (ai/gateway) ──▶ 응답+인용
```

| 컴포넌트 | 구현 | 핵심 |
|----------|------|------|
| RAG | `rag/{ingest,vectorstore,service}.py` | 청크·임베딩·검색, 인용 포함 |
| AI Gateway | `ai/gateway.py` + `ai/providers/` | 단일 인터페이스, provider 교체, 비용/PII/감사 통제점 |
| On-prem | `ai/providers/onprem_provider.py` | OpenAI 호환 엔드포인트, 코드변경 0 |
| SharePoint/Teams | `connectors/{graph_client,sharepoint}.py` | Graph 인증·재귀크롤·**권한 미러(fail-closed)** |
| 문서 추출 | `connectors/extract.py` | 텍스트·docx(stdlib)·pdf(pypdf), 확장 레지스트리 |
| Security Trimming | `rag/vectorstore.py`, `security/{acl,rbac}.py` | 검색 top-k **이전** ACL 트리밍 |

> Security Trimming = 문서 ACL을 청크에 스냅샷 → 사용자 principals와 교집합 없으면 랭킹 전 제거. SharePoint 권한을 원천 그대로 반영, 권한 조회 실패 시 공개 아닌 차단.

### 9.1 파생 뷰 (구현 완료)
- `v_customer_360` (`views/customer360.py`), `v_employee_performance` (`views/performance.py`), `v_inventory_status` (`views/inventory.py`), `v_pipeline` (`views/pipeline.py`) — 전부 Activity/엔티티 실시간 집계.

### 9.2 AI 에이전트 (4종 구현 완료)
- AS 트리아지 · 지식화 캡처 · 자동 팔로업(HITL) · **성과·마케팅 인사이트**(`agents/insights.py`, 읽기용 신호+요약). 분류는 결정적 규칙(`agents/rules.py`)이 권위, LLM은 서사 보강.

---

## 10. 구현 매핑 (로드맵 Phase ↔ 컴포넌트)

| Phase | 구현 컴포넌트 | 상태 |
|-------|-------------|:----:|
| P1 | 허브(Customer/Lead/Order/ProductionJob/Product/Activity), v_customer_360, **+RAG·Gateway·SharePoint·Security Trimming** | ✅ |
| P2 | AccountingPort+어댑터+정합대조, CalendarPort+양방향동기화, Transaction 미러 | ✅ |
| P3 | 지식화·팔로업·AS 트리아지·인사이트 에이전트, KnowledgeItem, 파생뷰 3종 | ✅ |
| P4 | L5 워크스페이스 프레임, 역할 프리셋, user preference | ⏳ |
| P5 | 감사·거버넌스 대시보드, 확산 런북 | ⏳ |

**프로덕션 하드닝 백로그**: pgvector 백엔드, 실 이벤트버스(NOTIFY/Redis)+에이전트 자동트리거, MCP 서버, 인증 미들웨어, RLS, 마케팅 광고 커넥터, 재고 이동 모델, 발송 어댑터.

---

## 11. 다음 단계
- P4 경험 레이어(역할별 워크스페이스) 또는 프로덕션 하드닝 백로그 착수
- 실 LLM/테넌트/SaaS 크레덴셜 연결 (provider 교체만으로 동작)
