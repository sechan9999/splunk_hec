# Unified Ops AX — 전사 통합 운영체계

소규모(~50인) 제조/판매업을 위한 전사 AX 운영체계. 단일 `Activity` 이벤트 스트림(SSOT) 위에 데이터 허브 · Enterprise AI Platform · SaaS 오케스트레이션 · AI 에이전트 · 역할별 경험 레이어 · 거버넌스를 얹은 **모듈러 모놀리스** 백엔드. 키·외부 서비스 없이 **오프라인에서 바로 실행/테스트**.

- **로드맵 P1~P5 전 단계 구현 완료** · 테스트 **57개** 통과 (오프라인) · FastAPI
- 기획: [plan](../docs/01-plan/features/unified-ops-ax.plan.md) · 아키텍처: [design](../docs/02-design/features/unified-ops-ax.design.md) · Gap분석: [analysis](../docs/03-analysis/unified-ops-ax.analysis.md) · 보고서: [report](../docs/04-report/unified-ops-ax.report.md) · 거버넌스: [GOVERNANCE.md](GOVERNANCE.md)

### 5-레이어 (설계서 §1)
```
L5 경험      역할별 워크스페이스 (app/experience) + /workspace/dashboard
L4 지능      AI 에이전트 4종 (app/agents) + AI Gateway (app/ai)
L3 허브      Activity 이벤트 스토어 SSOT + 파생뷰 (app/domain, app/views) + RAG (app/rag)
L2 통합      SaaS 어댑터·오케스트레이션 (app/connectors, app/orchestration) + 이벤트 아웃박스 (app/events)
거버넌스     감사·채택KPI·오너십 (app/governance) · 보안 (app/security)
```

## 요구사항 → 구현 매핑

| 확장 요구 | 구현 위치 |
|-----------|-----------|
| 사내 문서 이해 **Production-grade RAG** | `app/rag/` (ingest·vectorstore·service), `app/ai/embeddings.py` |
| 여러 LLM 통합 **AI Gateway** | `app/ai/gateway.py` + `app/ai/providers/` (anthropic·openai·onprem·fake) |
| Teams·SharePoint 연계 **Enterprise AI** | `app/connectors/sharepoint.py` (실제 Graph 연동: 인증·크롤·권한미러) + `graph_client.py` + 로컬 커넥터 |
| **Security Trimming** (권한) | `app/security/`, `app/rag/vectorstore.py` (검색 시 top-k 이전에 ACL 트리밍) |
| **On-prem AI** 확장 | `app/ai/providers/onprem_provider.py` (OpenAI 호환 엔드포인트, 코드 변경 0) |
| 데이터 허브 (P1 원안) | `app/domain/models.py` (Activity 이벤트 스토어), `app/views/customer360.py` |
| **회계/일정 SaaS 오케스트레이션 (P2)** | `app/connectors/{accounting,calendar}.py` (어댑터) + `app/orchestration/` (동기화·정합) |
| **AI 에이전트 레이어 (P3)** | `app/agents/` — AS 트리아지 · 지식화 캡처 · 자동 팔로업(HITL) · 성과·마케팅 인사이트 |
| **경험 레이어 (P4)** | `app/experience/workspace.py` (역할별 위젯 조립+개인화) + `/workspace/dashboard` 씬 클라이언트 |
| **하드닝: 이벤트 아웃박스+자동트리거** | `app/events/dispatch.py` (에이전트 이벤트 구독) |
| **하드닝: 인증 미들웨어** | `app/security/auth.py` (Bearer 토큰 → identity, role 서버 도출) |
| **거버넌스 (P5)** | `app/governance/` — 감사·채택KPI·데이터오너십·대시보드 (manager 전용) + `GOVERNANCE.md` 런북 |

## 빠른 시작

```bash
cd unified-ops-ax
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
pytest -q                                         # 전 테스트 오프라인 통과
uvicorn app.main:app --reload                     # http://localhost:8000/docs
```

키/외부 서비스 없이 기본값(`fake` LLM·임베딩, `memory` 벡터, SQLite)으로 동작. 실 LLM/Postgres/Graph/SaaS는 `.env`만 교체 — 절차·검증은 **[LIVE.md](LIVE.md)**.

```bash
python -m app.preflight    # 라이브 연동 상태 진단 (LLM·벡터·DB·Graph·SaaS)
```

## 핵심 개념

- **Activity 이벤트 스토어**: 모든 부서 행위가 한 테이블. 성과·회계정합·고객360°·인계자동화가 이 스트림의 파생. `place_order()` 하나가 주문+공정Job+이벤트 3종을 자동 생성.
- **Security Trimming**: 문서 ACL을 청크에 스냅샷 → 검색 시 사용자 principals와 교집합 없는 청크는 **랭킹 이전에 제거**. 가장 관련성 높은 문서라도 권한 없으면 절대 안 나옴(`tests/test_security_trimming.py`로 증명).
- **AI Gateway**: 단일 인터페이스, provider만 교체. 향후 비용 라우팅·PII 마스킹·감사로그의 단일 통제점.

## 데모: 폴더 인제스트 (Security Trimming 체험)

```bash
# docs_demo/ 에 .txt 파일과 옵션 사이드카 <name>.txt.acl (예: "grp:sales") 배치
curl -X POST localhost:8000/rag/ingest/folder -H "content-type: application/json" -d "{\"path\":\"docs_demo\"}"
curl -X POST localhost:8000/rag/query -H "content-type: application/json" -d "{\"query\":\"...\",\"role\":\"sales\"}"
```

## SharePoint / Teams 커넥터 (Microsoft Graph)

실제 Graph 연동 구현됨 — client-credentials 인증(`graph_client.py`), 드라이브 재귀 크롤, **권한 미러링**(`map_permissions`), fail-closed(권한 조회 실패 시 공개 아닌 차단). `.env`에 `GRAPH_*`·`SHAREPOINT_SITE_ID`(또는 `TEAMS_GROUP_ID`) 설정 후:

```bash
curl -X POST localhost:8000/rag/ingest/sharepoint    # site 문서 전체 인제스트(ACL 포함)
curl -X POST localhost:8000/rag/ingest/teams         # Team 파일(그룹 기본 드라이브)
```

권한 매핑: 사용자→`usr:<id>`, 그룹→`grp:<id>`, SP그룹→`sgrp:<id>`, 조직 링크→`grp:all`, 익명 링크→공개(`[]`), 조회 불가→`grp:__no_access__`. 라이브 테넌트 없이 `httpx.MockTransport`로 크롤·페이지네이션·권한매핑·트리밍 전 경로를 테스트(`tests/test_sharepoint_connector.py`).

**문서 추출**(`extract.py`): 텍스트(txt/md/csv/html/json…)는 native, **`.docx`는 stdlib**(zipfile+ElementTree, lxml 불필요), **`.pdf`는 pypdf**. 손상 파일·미설치 라이브러리는 해당 파일만 skip(로깅)하고 크롤은 계속. 바이너리는 다운로드 전 확장자로 필터. 새 포맷은 `BINARY_EXTRACTORS`에 등록만 하면 됨.

앱 registration 권한(application, admin-consent): `Sites.Read.All`, `Files.Read.All`, `Group.Read.All`.

## 회계 / 일정 SaaS 오케스트레이션 (P2)

어댑터 패턴으로 SaaS를 코어 밖에 격리. Fake 어댑터로 오프라인 실행/테스트. `.env`의 `ACCOUNTING_PROVIDER`/`CALENDAR_PROVIDER`만 교체하면 실 SaaS 연동.

```bash
curl -X POST localhost:8000/ops/accounting/sync       # 주문 -> 회계 SaaS 전표 미러(멱등)
curl      localhost:8000/ops/accounting/reconcile     # 정합 대조: integrity_rate, missing, mismatch
curl -X POST localhost:8000/ops/schedule -d '{"title":"AS 방문","start":"2026-08-05T10:00:00+00:00"}'
curl -X POST localhost:8000/ops/calendar/push         # 로컬 -> 캘린더 SaaS
curl -X POST localhost:8000/ops/calendar/pull         # 캘린더 SaaS -> 로컬
```

- **회계**: 아웃박스 패턴 — `order.placed`(진실원천)에서 미러 없는 주문만 전표 전송 후 `Transaction` 미러 생성. **멱등**(재실행해도 중복 없음). `reconcile`은 주문 기대금액 vs 미러를 대조해 `integrity_rate`(목표 ≥0.99)·missing·mismatch·orphan 산출. 미러 시 `transaction.posted` 이벤트를 남겨 고객 360°에 반영.
- **일정**: `ScheduleEvent` ↔ SaaS 양방향. push는 external_id 부여, pull은 external_id로 upsert(중복 방지). 충돌은 updated_at 기준 last-write-wins.
- **환불/취소**: `POST /hub/orders/{id}/cancel` → `POST /ops/accounting/refund/{id}`. 취소 주문은 reconcile 기대금액 0(sale−refund=0)으로 정합 유지.
- 어댑터: 회계 = Fake / **QuickBooks(실구현)** / 더존(문서화 셸), 일정 = Fake / **MS Graph(실구현)** / Google(스텁). QuickBooks·MS Graph는 MockTransport로 검증됨. 실연동은 `.env` 크레덴셜만 — [LIVE.md](LIVE.md).

## AI 에이전트 레이어 (P3)

이벤트에 반응해 **초안을 생성**하는 에이전트. 안전 원칙: 분류/라우팅은 **결정적 규칙**(`agents/rules.py`, 오프라인 안전 폴백)이 결정하고 LLM은 서사만 보강, 모든 산출은 `source=agent` 이벤트로 기록, **외부 발송·중요 액션은 사람 승인(HITL)**.

```bash
curl -X POST localhost:8000/agents/triage/{ticket_id}          # AS 접수 분류·심각도·담당 배정
curl -X POST localhost:8000/agents/knowledge/{ticket_id}       # 해결 티켓 -> 지식화 draft + RAG 인덱싱
curl -X POST localhost:8000/agents/followup/order/{order_id}   # 배송 후 팔로업 초안(발송 안 함)
curl -X POST localhost:8000/agents/followup/{followup_id}/approve   # 사람 승인 -> 발송(followup.sent)
```

| 에이전트 | 트리거 | 산출 | 승인 |
|----------|--------|------|------|
| **AS 트리아지** | `as.opened` | 카테고리·심각도 + 최소부하 담당자 배정 | 자동(내부·가역, override 가능) |
| **지식화 캡처** | `as.resolved` | 구조화 KnowledgeItem(draft) + RAG 인덱싱 → 검색 루프 폐쇄 | 자동(리뷰 큐) |
| **자동 팔로업** | `delivery.done` | 고객 맞춤 메시지 **초안** | **사람 승인 후 발송(HITL)** |

핵심: 에이전트는 원본 데이터를 침묵 수정하지 않고, 팔로업은 **절대 스스로 발송하지 않음** — `approve_and_send`(사람 게이트)에서만 `followup.sent` 발생. **발송 어댑터**(`connectors/notify.py`, Fake/Console/SMTP/Twilio)가 이 승인 지점에 연결되어, 승인 후 고객 연락처(PII 복호화)로 실제 발송(`NOTIFIER_PROVIDER`). 연락처 없으면 `delivered:false`로 기록.

## 경험 레이어 (P4) + 하드닝

역할별 워크스페이스는 **같은 SSOT, 다른 창** — 위젯이 파생 뷰에 바인딩되고 role로 게이팅, 개인 레이아웃으로 조립.

```bash
tok=$(curl -sX POST localhost:8000/hub/employees/{id}/token | jq -r .token)
curl -H "Authorization: Bearer $tok" localhost:8000/workspace/me       # 역할별 조립 워크스페이스
curl -H "Authorization: Bearer $tok" -X PUT localhost:8000/workspace/me/layout -d '{"widgets":["insights","pipeline"]}'
# 브라우저: localhost:8000/workspace/dashboard (토큰 입력 → 렌더)
```

- **인증**(`security/auth.py`): `Authorization: Bearer <token>` → Employee 조회 → role·principals **서버 도출**. role을 요청 파라미터로 받지 않음.
- **이벤트 아웃박스 + 워커**(`events/dispatch.py`, `worker.py`): 업무 트랜잭션은 Activity만 기록. **이벤트 워커**(`EVENT_WORKER_ENABLED=1`)가 별도 트랜잭션으로 아웃박스를 지속 드레인하며 에이전트 자동 트리거(as.opened→트리아지, delivery.done→팔로업, as.resolved→지식화). `Activity.dispatched`로 멱등, 중첩 커밋 없음. 앱 내 스레드 또는 독립 프로세스(`python -m app.worker`). 수동 1회: `POST /ops/dispatch`. 상태: `GET /ops/worker/status`.
- **RBAC 방어**: 저장된 레이아웃도 조회 시 role로 재필터(권한 밖 위젯 제거).

## 거버넌스 (P5)

불변 Activity 스트림 위의 **조회·통제 계층**(별도 로그 시스템 불필요). manager 전용. 상세 절차는 [GOVERNANCE.md](GOVERNANCE.md).

```bash
curl -H "Authorization: Bearer $mtok" localhost:8000/governance/dashboard    # 종합
curl -H "Authorization: Bearer $mtok" "localhost:8000/governance/audit?source=agent&since_days=7"
curl -H "Authorization: Bearer $mtok" localhost:8000/governance/adoption      # 채택 KPI
curl -H "Authorization: Bearer $mtok" -X POST localhost:8000/governance/ownership -d '{"domain":"accounting","owner_employee_id":"<id>","classification":"confidential"}'
```

- **감사 추적**: type·actor·subject·`source`(agent/app/saas)·기간 필터 — 자동/수동 액션 추적.
- **채택 KPI**: DAU/직원, HITL 승인율, 지식 커버리지, 회계 정합률 (기획서 §2 매핑).
- **데이터 오너십**: 도메인별 오너·분류, 미지정 도메인 노출.
- 비-manager 접근 → 403 (`tests/test_governance.py`로 증명).

## 프로덕션 전환 체크리스트

구현 완료(오프라인 검증)된 것과, 라이브 인프라/크레덴셜이 필요한 잔여를 구분한다.

**구현 완료** — 어댑터·스텁·outline까지 존재, provider/크레덴셜만 교체:
- 인증: Bearer 토큰 → identity, role 서버 도출 (`security/auth.py`)
- **RLS**(`security/rls.py`): 역할별 행 접근제어 — sales는 자기 고객, AS는 배정/미배정 티켓, manager/accounting은 전체. 고객 상세/360°는 `can_view_customer` 미충족 시 403.
- **PII 암호화**(`security/pii.py`): Customer email/phone를 at-rest 암호화(`enc:v1:`), 권한자 조회 시에만 복호화. 키 없으면 no-op(dev). *stdlib 키스트림 — 프로덕션은 AES-GCM/KMS 권장.*
- 이벤트 아웃박스 + 에이전트 자동트리거 (`events/dispatch.py`, `Activity.dispatched`)
- docx/pdf 추출, Security Trimming, 회계 정합대조·환불, 일정 양방향, QuickBooks/MS Graph 어댑터

**라이브/하드닝 잔여**:
- `DATABASE_URL` → Postgres, `VECTOR_BACKEND=pgvector` (embedding 컬럼 + `app/rag/vectorstore.py` SQL 구현)
- `DEFAULT_LLM_PROVIDER`/`EMBEDDING_PROVIDER` → anthropic/openai/onprem
- SharePoint/Teams: 라이브 테넌트 크레덴셜 + 추가 포맷(xlsx/pptx, 스캔 PDF는 OCR) + `/delta` 증분
- 회계/일정: 실 SaaS 어댑터(더존/QuickBooks/MS Graph/Google) + 동기화 스케줄러 + refund/취소
- 이벤트 버스: in-process 아웃박스 → Postgres NOTIFY / Redis + 백그라운드 워커
- 프로덕션 강화: Postgres RLS 정책(앱 계층 RLS 구현됨) · AES-GCM/KMS(PII 앱 암호화 구현됨) · MCP 서버 · 이메일/SMS·마케팅 광고 어댑터 · 더존/Google 어댑터

## 다음 단계 (로드맵)

**P1~P5 전 로드맵 구현 완료.** 남은 것은 프로덕션 하드닝(RLS·PII·pgvector·실 이벤트버스·MCP·발송/마케팅 어댑터)과 라이브 연동(provider/크레덴셜 교체). 상세는 설계서 §10 및 `GOVERNANCE.md`.
