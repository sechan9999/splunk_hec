# Unified Ops AX — 라이브 연동 가이드

기본값은 오프라인(fake). 아래 크레덴셜을 `.env`에 넣으면 **코드 변경 없이** 라이브로 전환된다. 각 단계 후 프리플라이트로 검증한다.

```bash
python -m app.preflight            # 또는  GET /ops/preflight
```
`status`: `fake`(오프라인) · `configured`(크레덴셜 있음) · `ok`(연결 확인) · `missing`(선택 미설정) · `error`(연결 실패). `ready:false`면 `attention` 서브시스템의 `error`를 먼저 해결.

> 프리플라이트는 상태만 노출(비밀값 없음). LLM 라이브 호출(비용 발생)은 하지 않고 크레덴셜 존재만 확인하며, DB는 무료라 실제 연결까지 확인한다.

---

## 1. LLM / 임베딩
```
DEFAULT_LLM_PROVIDER=anthropic        # anthropic | openai | onprem
ANTHROPIC_API_KEY=sk-...
ANTHROPIC_MODEL=claude-opus-4-8
# 또는 온프렘(OpenAI 호환 엔드포인트: Ollama/vLLM)
# DEFAULT_LLM_PROVIDER=onprem
# ONPREM_BASE_URL=http://gpu-host:11434
EMBEDDING_PROVIDER=openai             # 실 임베딩 시
OPENAI_API_KEY=sk-...
```
검증: `POST /gateway/chat {"message":"ping"}` → `provider` 확인.

### 무키(Keyless) 완전 로컬 스택 — Ollama만으로 (API 키 0)
```
DEFAULT_LLM_PROVIDER=onprem
ONPREM_BASE_URL=http://localhost:11434
ONPREM_MODEL=llama3                   # 또는 gemma3:4b 등 받아둔 모델
EMBEDDING_PROVIDER=onprem
ONPREM_EMBEDDING_MODEL=nomic-embed-text
```
`ollama pull llama3 && ollama pull nomic-embed-text` 후 preflight → `llm: ok`, `embeddings: ok (keyless)`. LLM 추론 + RAG 의미검색까지 전부 로컬, 키·비용 0. (라이브 검증됨: gemma3:4b + nomic-embed-text로 RAG 근거답변·인용 정상.)

## 2. Postgres + pgvector (벡터 백엔드)
```
DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/unifiedops
VECTOR_BACKEND=pgvector
```
```bash
pip install psycopg2-binary pgvector    # requirements의 주석 해제
```
`PgVectorStore`가 최초 기동 시 `vector` 확장과 `rag_vectors` 테이블(embedding vector 컬럼)을 자체 생성. Security Trimming은 SQL(`acl ?| principals`)로 수행. **라이브 Postgres에서만 검증됨** — 오프라인 테스트는 memory 백엔드 사용.
검증: `GET /ops/preflight` → `database: ok`, `vector: configured`.

## 3. SharePoint / Teams (Microsoft Graph)
Azure AD 앱 등록(application 권한, admin-consent): `Sites.Read.All`, `Files.Read.All`, `Group.Read.All` (+ 캘린더는 `Calendars.ReadWrite`).
```
GRAPH_TENANT_ID=...
GRAPH_CLIENT_ID=...
GRAPH_CLIENT_SECRET=...
SHAREPOINT_SITE_ID=contoso.sharepoint.com,<siteGuid>,<webGuid>
TEAMS_GROUP_ID=<m365-group-id>
```
검증: `POST /rag/ingest/sharepoint` → 인제스트된 문서·ACL 확인.

## 4. 캘린더 (MS Graph)
```
CALENDAR_PROVIDER=msgraph
CALENDAR_USER_ID=ops@contoso.com       # 대상 메일박스
```
검증: `POST /ops/calendar/push` → external_id 부여, `POST /ops/calendar/pull` → 역동기화.

## 5. 회계 SaaS

### QuickBooks Online — 실구현 완료
```
ACCOUNTING_PROVIDER=quickbooks
QBO_ACCESS_TOKEN=...          # QBO OAuth2 auth-code 플로우로 사용자가 획득 (refresh는 caller 책임)
QBO_REALM_ID=...
QBO_BASE_URL=https://quickbooks.api.intuit.com   # 샌드박스: https://sandbox-quickbooks.api.intuit.com
QBO_CUSTOMER_REF=1           # 기본 CustomerRef (운영은 order→QBO customer 매핑 필요)
```
sale→Invoice, refund→CreditMemo, list→`SELECT * FROM Invoice`. 검증: `POST /ops/accounting/sync` → `GET /ops/accounting/reconcile` `integrity_rate`.

### 더존(Douzone) — 문서화 셸
제품(Bizbox/iCUBE/WEHAGO)·계약별 API가 달라 스펙 확정 후 구현. `DouzoneAdapter` docstring의 전표 등록/원장 조회 outline대로 `post_transaction`/`list_transactions`를 채우면 동일 Port로 동작.

### 환불/취소
`POST /hub/orders/{id}/cancel` → `POST /ops/accounting/refund/{id}`. 취소 주문은 reconcile에서 기대금액 0 처리(sale-refund=0)되어 정합 유지.

---

## 6b. 이벤트 워커 (자동화)
```
EVENT_WORKER_ENABLED=true          # 아웃박스 자동 드레인 + 에이전트 자동 트리거
EVENT_WORKER_INTERVAL=2.0
```
앱 기동 시 스레드로 자동 실행되거나, 스케일아웃 시 독립 프로세스로:
```bash
python -m app.worker
```
검증: `GET /ops/worker/status` → `running:true`, `stats.triggered` 증가. 프로덕션은 폴러를 Postgres LISTEN/NOTIFY 또는 Redis Streams로 승격 가능(동일 `dispatch_pending` 드레인, 아웃박스가 진실원천).

## 6c. 발송 어댑터 (팔로업 HITL 발송)
```
NOTIFIER_PROVIDER=smtp                # fake | console | smtp | twilio
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=ops@company.com
SMTP_PASSWORD=...
SMTP_FROM=ops@company.com
# 또는 SMS
# NOTIFIER_PROVIDER=twilio
# TWILIO_ACCOUNT_SID=AC...
# TWILIO_AUTH_TOKEN=...
# TWILIO_FROM_NUMBER=+1...
```
승인(`POST /agents/followup/{id}/approve`) 시에만 고객 연락처(PII 복호화)로 발송. 에이전트는 절대 자동 발송하지 않음. 검증: 승인 응답 `delivered:true`, `message_id`.

## 라이브 전환 순서 (권장)
1. LLM 키 (가장 즉효) → `/gateway/chat`, `/rag/query` 품질 확인
2. Postgres+pgvector → 데이터 영속성·검색 성능
3. Graph(SharePoint/캘린더) → 사내 문서·일정
4. 회계 어댑터 실구현 → 전표 자동화
5. 운영 하드닝: 실 이벤트버스(NOTIFY/Redis)+워커, RLS, PII 암호화, 발송 어댑터

각 단계는 독립적으로 켤 수 있고(fake와 혼용 가능), 프리플라이트로 상태를 확인하며 점진 전환한다.
