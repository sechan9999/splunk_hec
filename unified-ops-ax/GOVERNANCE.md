# Unified Ops AX — 거버넌스 & 확산 런북 (P5)

전사 AX 운영체계의 정착·확산·통제 절차. 거버넌스는 별도 로그 시스템이 아니라 **불변 Activity 스트림 위의 조회 계층**이다.

## 1. 확산 로드맵 (Crawl-Walk-Run)

| 단계 | 대상 | Gate |
|------|------|------|
| 파일럿 | 통증 큰 1~2개 부서(권장 CRM+주문) | DAU 목표 도달, 이탈 없음 |
| 확장 | 공정·AS·회계 순차 편입 | 도메인별 데이터 정합 99%+ |
| 전사 | 전 부서 + 개인 워크스페이스 정착 | DAU/직원 70%+ |
| 정착 | 에이전트 자동화 신뢰 확보 | HITL 승인율 안정, 지식 커버리지 80% |

각 단계는 독립적 가치 산출 후 다음으로. 빅뱅 금지.

## 2. 채택 KPI (`GET /governance/adoption`)

| KPI | 정의 | 목표 |
|-----|------|------|
| DAU/직원 | 최근 N일 활동한 직원 / 전체 | 70%+ |
| 활동량(by_source) | app/agent/saas/calendar별 이벤트 | 추세 모니터 |
| HITL 승인율 | followup sent / drafted | 안정적(과도한 반려는 초안 품질 신호) |
| 지식 커버리지 | KnowledgeItem / 해결된 AS 티켓 | 80%+ |
| 회계 정합률 | reconcile integrity_rate | 99%+ |

착수 전 baseline 실측(기획서 §2) → 개선율은 실측 대비 산정.

## 3. 데이터 오너십 (`/governance/ownership`)

도메인별 오너·분류(public/internal/confidential) 등록. P0에서 9개 도메인 전부 오너 지정 필수.

```bash
curl -X POST /governance/ownership -H "Authorization: Bearer <manager>" \
  -d '{"domain":"accounting","owner_employee_id":"<id>","classification":"confidential"}'
```

미지정 도메인은 대시보드 `coverage.unassigned`로 노출 → 정착 전 0건화.

## 4. 보안 태세 (`security_posture`)

- **RBAC**: role → principals, 최소권한
- **Security Trimming**: 문서 ACL ∩ principals, 검색 top-k 이전 차단
- **감사 로그**: 불변 Activity 스트림(누가·언제·무엇) — 삭제/수정 불가
- **인증**: Bearer 토큰, role 서버 도출
- **AI 안전**: 에이전트 초안만, 외부 발송·자금·계약은 HITL

## 5. 감사 절차 (`GET /governance/audit`)

이슈 조사 시 type·actor·subject·source·기간으로 필터. 에이전트 행위는 `source=agent`로 구분되어 자동/수동 액션 추적 가능.

```bash
curl "/governance/audit?source=agent&since_days=7" -H "Authorization: Bearer <manager>"
```

## 6. 미착수 하드닝 (프로덕션 전)

RLS(행 수준 접근제어) · PII 암호화 · pgvector · 실 이벤트버스(NOTIFY/Redis) · MCP 서버 · 이메일/SMS 발송 어댑터 · 마케팅 광고 커넥터. 라이브 전환은 provider/크레덴셜 교체만으로 동작.

## 7. 대시보드
- API: `GET /governance/dashboard` (manager 전용) — adoption + ownership + recent_audit + security_posture 종합
- 워크스페이스 씬클라이언트: `/workspace/dashboard`
