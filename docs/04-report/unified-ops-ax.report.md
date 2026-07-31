# Unified Ops AX — 최종 완료 보고서 (Report)

- **Feature**: `unified-ops-ax`
- **최종 갱신**: 2026-07-31
- **대상 조직**: 소규모 제조/판매업 (~50인)
- **구축 전략**: 하이브리드 (핵심 허브 자체 구축 + 회계·일정·문서 SaaS 연동)
- **최종 상태**: **P1~P5 전 로드맵 + 프로덕션 하드닝 + 무키 완전 로컬 스택 완성**
- **검증**: 유닛 **97개** · 스모크 **15개**(fake·onprem 양쪽) 통과 · 로컬 Ollama 라이브 검증
- **저장소**: `github.com/sechan9999/splunk_hec` (master), `0a44706 … 4ab3969`
- **규모**: 소스 76개 · 테스트 22파일

```
[Plan]✅ [Design]✅ [Do]✅(P1·P2·P3) [Check]✅88%→[Act-1]✅93% [Report]✅
        + P4 경험레이어 · P5 거버넌스 · 하드닝 12종 · 무키 로컬 스택
```

---

## 1. Executive Summary

부서별로 흩어진 업무 흐름·데이터를 **단일 `Activity` 이벤트 스트림(SSOT)** 위로 통합한 전사 AX 운영체계를, 오프라인에서 즉시 실행·검증되는 **모듈러 모놀리스 FastAPI 백엔드**로 구현 완료했다. 성과관리·회계정합·고객360°·인계자동화가 전부 이 한 스트림의 파생으로 동작하며, 그 위에 Enterprise AI Platform(RAG·게이트웨이·문서커넥터)·SaaS 오케스트레이션·AI 에이전트·역할별 경험 레이어·거버넌스를 얹었다. 마지막으로 **API 키·비용 0의 완전 로컬 AI 스택**(로컬 Ollama)까지 라이브 검증했다.

---

## 2. 구현 범위 (Phase + 하드닝)

### 로드맵 P1~P5
| Phase | 산출 | 상태 |
|-------|------|:----:|
| P1 | 데이터 허브(Activity 이벤트 스토어) + Enterprise AI Platform(RAG·멀티LLM Gateway·SharePoint/Teams 커넥터·Security Trimming·docx/pdf 추출) | ✅ |
| P2 | 회계·일정 SaaS 오케스트레이션(어댑터 + 99% 정합 대조 + 양방향 동기화) | ✅ |
| P3 | AI 에이전트 4종(AS 트리아지·지식화·팔로업 HITL·성과인사이트) + 파생 뷰 4종 | ✅ |
| P4 | 역할별 워크스페이스 조립 + 대시보드 씬클라이언트 | ✅ |
| P5 | 감사·채택KPI·데이터오너십·거버넌스 대시보드 + 확산 런북 | ✅ |

### 프로덕션 하드닝
| 항목 | 구현 |
|------|------|
| 인증 미들웨어 | Bearer 토큰 → identity, role 서버 도출 (`security/auth.py`) |
| 이벤트 아웃박스 + 워커 | `Activity.dispatched` 멱등, 백그라운드 드레인 → 에이전트 자동 트리거 (`events/dispatch.py`, `worker.py`) |
| RLS | 역할별 행 접근제어, `can_view_customer` 403 (`security/rls.py`) |
| PII 암호화 | email/phone at-rest 암호화(`enc:v1:`), 권한자만 복호화 (`security/pii.py`) |
| 회계 어댑터 | QuickBooks(실구현)·더존(WEHAGO)·환불/취소 흐름 |
| 캘린더 어댑터 | MS Graph(실구현)·Google(실구현) |
| 마케팅 커넥터 | Meta Ads 성능/애그리게이트 (`connectors/marketing_ads.py`) |
| 발송 어댑터 | SMTP·Twilio, 팔로업 HITL 승인 지점 연결 (`connectors/notify.py`) |
| pgvector | 자체 `rag_vectors` 테이블 + SQL Security Trimming |
| MCP 서버 | 허브를 MCP 도구 7종으로 노출(JSON-RPC stdio + HTTP 브리지) (`app/mcp/`) |
| Postgres RLS 정책 | `scripts/postgres_rls_policies.sql` (앱 계층 RLS와 병행) |
| 프리플라이트 | 서브시스템 상태 진단(비밀값 노출 없음) (`app/preflight.py`) |

### 무키 완전 로컬 AI 스택
- **OnPremProvider**(LLM) + **OnPremEmbedder**(임베딩): httpx 직접, OpenAI호환→Ollama네이티브 폴백, **API 키 불필요**.
- `.env` 5줄로 로컬 Ollama(gemma3:4b + nomic-embed-text)만으로 LLM 추론 + RAG 의미검색 + 전 에이전트 동작.

---

## 3. 핵심 설계 결정 & 검증

| 결정 | 근거 | 검증 |
|------|------|------|
| 단일 Activity 이벤트 스트림 = SSOT | 5개 도메인을 한 테이블이 먹임, 파생 뷰로 사일로 제거 | 360° 타임라인 E2E |
| Security Trimming (top-k 이전 ACL 필터) | SharePoint식 권한 반영, 유출 차단 | 영업이 회계문서 검색 불가(실 임베딩에서도) |
| Fail-closed 권한 매핑 | 조회 실패 시 공개 아닌 차단 | 테스트 증명 |
| 규칙이 라우팅 결정, LLM은 서사만 | 환각이 배정 좌우 못함 + 오프라인 폴백 | 분류 유닛테스트 |
| HITL 발송 게이트 + 발송 어댑터 | 외부 발송은 사람 승인 후에만 | 초안 후 미발송 → 승인 후 delivered |
| 이벤트 아웃박스(별도 트랜잭션) | 중첩 커밋 회피, 멱등 자동 트리거 | 워커 드레인 → as.triaged 자동 |
| MCP는 읽기+안전액션만 노출 | 외부 발송·자금 액션은 HITL 유지 | tools/list 7종, 발송/환불 제외 |
| PII는 stdlib 키스트림 | 긴 venv 경로에서 native crypto DLL 실패 회피 | at-rest enc:v1: 확인 |
| 무키 로컬 provider | 유료 키 없이 로컬 Llama 구동 | 라이브 gemma3:4b + nomic-embed |

---

## 4. 품질 & 검증

- **유닛 97개** 통과 (규칙·어댑터·MCP 프로토콜·RLS·PII·엣지케이스)
- **스모크 15개**(`verify.py`) 통과 — 한 고객 여정(주문→공정→회계→AS→지식화→팔로업)을 관통하는 E2E
  - **fake 모드**(오프라인, 키 0): 15/15
  - **onprem 모드**(로컬 Ollama 라이브): 15/15, preflight `LLM=ok keyless`
- **라이브 검증**: gemma3:4b(LLM) + nomic-embed-text(임베딩)로 RAG 근거답변·인용, 패러프레이즈 의미검색 정상

재현:
```bash
pytest -q                                   # 유닛 97
python verify.py                            # 스모크 15 (오프라인)
DEFAULT_LLM_PROVIDER=onprem EMBEDDING_PROVIDER=onprem python verify.py   # 로컬 Ollama 라이브
```

---

## 5. 배운 점 (Lessons Learned)

1. **이벤트 스토어 우선 설계가 통합의 물리적 실체** — 도메인 추가가 값싸짐(성과·회계·360°는 파생).
2. **LLM은 서사, 규칙은 결정** — 오프라인 결정성 + 프로덕션 가드레일 동시 확보.
3. **어댑터 패턴 + Fake 구현** — 오프라인 테스트와 락인 방지를 동시 해결(회계·캘린더·발송·마케팅·벡터·LLM·임베딩 전부 동일 패턴).
4. **환경 제약이 더 나은 설계로** — lxml/native-crypto DLL 실패 → docx stdlib 파싱, PII stdlib 키스트림.
5. **수치보다 정합** — A4(자동 트리거)를 억지 inline이 아닌 아웃박스로 올바르게 해결.
6. **무키 로컬화** — provider 추상화 덕에 로컬 Ollama로 유료 키 없이 전 파이프라인 구동.

---

## 6. 잔여 작업 (정직하게)

오프라인으로 구현 가능한 항목은 사실상 소진. 남은 것은 **실 API 스펙·인프라·크레덴셜**이 필요하다:
- 더존/Google/Meta 어댑터의 **실 테넌트 연동 검증**(코드·outline 존재, 실 계약 스펙 필요)
- pgvector·Postgres RLS 정책의 **라이브 Postgres 검증**
- 프로덕션 강화: PII를 AES-GCM/KMS로, 이벤트버스를 NOTIFY/Redis로 승격, SMTP/Twilio 실 발송

라이브 전환은 `.env` 크레덴셜 + `python -m app.preflight`로 검증(상세 `LIVE.md`).

---

## 7. 결론

전사 AX의 **실행 청사진 + 동작하는 전 계층 백엔드**가 완성되어, 오프라인·로컬 라이브 양쪽에서 검증된 채 GitHub master에 있다. 로컬 Ollama만 있으면 **키·비용 0으로 즉시 사용 가능**하며, 실 SaaS 연동은 크레덴셜 연결만 남았다. PDCA 사이클을 정식 종료한다.

- 계획: `docs/01-plan/features/unified-ops-ax.plan.md`
- 설계: `docs/02-design/features/unified-ops-ax.design.md`
- 분석: `docs/03-analysis/unified-ops-ax.analysis.md`
- 코드/운영: `unified-ops-ax/` (`README.md`, `LIVE.md`, `GOVERNANCE.md`, `verify.py`)
