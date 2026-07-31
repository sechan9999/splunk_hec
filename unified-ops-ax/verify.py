"""Offline verification — exercises every major subsystem end-to-end with the
default fake/offline providers (no keys, no network) and prints a pass/fail
checklist. Run:  python verify.py   (exit 0 = all green)

Complements the unit suite: run `pytest -q` for the 87 granular tests."""
from __future__ import annotations

import json
import os
import sys
import tempfile

# Configure an isolated environment BEFORE importing the app. DB/vector/PII are
# forced for isolation; AI/notifier providers respect pre-set env (setdefault),
# so `DEFAULT_LLM_PROVIDER=onprem ... python verify.py` runs against local Ollama.
_fd, _db = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ.update({
    "DATABASE_URL": f"sqlite+pysqlite:///{_db}",
    "VECTOR_BACKEND": "memory",
    "PII_KEY": "verify-secret",  # exercise PII encryption
})
os.environ.setdefault("DEFAULT_LLM_PROVIDER", "fake")
os.environ.setdefault("EMBEDDING_PROVIDER", "fake")
os.environ.setdefault("NOTIFIER_PROVIDER", "fake")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))


def main() -> int:
    with TestClient(app) as c:
        H = lambda t: {"Authorization": f"Bearer {t}"}

        # 0. preflight — ready, PII engaged; LLM either fake or a live keyless/configured provider
        pf = c.get("/ops/preflight").json()
        by = {x["subsystem"]: x["status"] for x in pf["checks"]}
        check(f"프리플라이트 (ready · LLM={by['llm']} · PII on)",
              pf["ready"] and by["llm"] in ("fake", "ok", "configured")
              and by["vector"] == "ok" and by["pii"] == "configured",
              f"mode={pf['mode']}")

        # 1. actors
        mgr = c.post("/hub/employees", json={"name": "김대표", "role": "manager"}).json()["id"]
        mtok = c.post(f"/hub/employees/{mgr}/token").json()["token"]
        prod = c.post("/hub/employees", json={"name": "박기사", "role": "production"}).json()["id"]
        s1 = c.post("/hub/employees", json={"name": "이영업", "role": "sales"}).json()["id"]
        t1 = c.post(f"/hub/employees/{s1}/token").json()["token"]
        s2 = c.post("/hub/employees", json={"name": "최영업", "role": "sales"}).json()["id"]
        t2 = c.post(f"/hub/employees/{s2}/token").json()["token"]
        pid = c.post("/hub/products", json={"sku": "P1", "name": "밸브", "unit_price": 100, "stock_qty": 5}).json()["id"]
        cid = c.post("/hub/customers", json={"name": "대성정밀", "email": "ceo@daesung.co.kr", "owner_employee_id": s1}).json()["id"]
        check("액터/제품/고객 생성 + 토큰 발급", bool(mtok and t1 and pid and cid))

        # 2. PII encrypted at rest
        import sqlite3
        raw = sqlite3.connect(_db).execute("SELECT email FROM customers WHERE id=?", (cid,)).fetchone()[0]
        check("PII at-rest 암호화 (enc:v1:)", raw.startswith("enc:v1:"), raw[:16])

        # 3. order -> production auto-job -> accounting sync -> reconcile
        oid = c.post("/hub/orders", json={"customer_id": cid, "lines": [{"product_id": pid, "qty": 2}]}).json()["id"]
        c.post("/ops/accounting/sync")
        rec = c.get("/ops/accounting/reconcile").json()
        check("주문→공정→회계 정합 (integrity 1.0)", rec["integrity_rate"] == 1.0 and rec["healthy"])

        # 4. AS ticket -> event dispatch -> auto triage
        tid = c.post("/hub/as-tickets", json={"customer_id": cid, "summary": "전원 부품 고장"}).json()["id"]
        disp = c.post("/ops/dispatch").json()
        types = {a["type"] for a in c.get("/governance/audit", headers=H(mtok)).json()}
        check("이벤트 아웃박스→자동 트리아지 (as.triaged)", disp["triggered"] >= 1 and "as.triaged" in types)

        # 5. resolve -> knowledge capture -> RAG retrievable
        c.post(f"/hub/as-tickets/{tid}/resolve", json={"resolution": "커넥터 교체"})
        c.post("/ops/dispatch")  # drain as.resolved -> knowledge agent
        q = c.post("/rag/query", json={"query": "전원 부품 고장", "role": "as"}).json()
        check("지식화→RAG 검색 루프", any("전원" in (cit.get("title") or "") for cit in q["citations"]))

        # 6. deliver -> followup draft -> HITL approve+send
        c.post(f"/hub/orders/{oid}/deliver")
        c.post("/ops/dispatch")  # delivery.done -> followup draft
        fu = c.get("/governance/audit", headers=H(mtok)).json()
        fu_drafted = any(a["type"] == "followup.drafted" for a in fu)
        # approve the draft
        from app.db import SessionLocal
        from app.domain.models import FollowUp
        with SessionLocal() as s:
            fid = s.query(FollowUp).first().id
        appr = c.post(f"/agents/followup/{fid}/approve").json()
        check("배송→팔로업 초안(자동)→HITL 발송", fu_drafted and appr["status"] == "sent" and appr["delivered"])

        # 7. RAG Security Trimming
        c.post("/rag/ingest", json={"title": "Payroll", "content": "payroll tax ledger salary", "acl": ["grp:accounting"]})
        c.post("/rag/ingest", json={"title": "Handbook", "content": "vacation policy onboarding", "acl": []})
        sales_q = c.post("/rag/query", json={"query": "payroll tax ledger salary", "role": "sales"}).json()
        check("Security Trimming (영업이 회계문서 검색 불가)",
              all(cit["title"] != "Payroll" for cit in sales_q["citations"]))

        # 8. RLS — sales sees only own customer; other sales blocked
        s1_view = c.get("/hub/customers/" + cid, headers=H(t1))
        s2_view = c.get("/hub/customers/" + cid, headers=H(t2))
        check("RLS + PII 복호화 (소유자만, 타인 403)",
              s1_view.status_code == 200 and s1_view.json()["email"] == "ceo@daesung.co.kr" and s2_view.status_code == 403)

        # 9. role-based workspace
        ws = c.get("/workspace/me", headers=H(mtok)).json()
        ids = {w["id"] for w in ws["widgets"]}
        check("역할별 워크스페이스 (manager 위젯)", {"pipeline", "performance", "accounting_health"} <= ids)

        # 10. governance dashboard (manager only)
        gov = c.get("/governance/dashboard", headers=H(mtok))
        gov_denied = c.get("/governance/dashboard", headers=H(t1)).status_code
        check("거버넌스 대시보드 (manager 전용, 영업 403)", gov.status_code == 200 and gov_denied == 403)

        # 11. cancel + refund keeps integrity
        c.post(f"/hub/orders/{oid}/cancel")
        c.post(f"/ops/accounting/refund/{oid}")
        rec2 = c.get("/ops/accounting/reconcile").json()
        check("취소+환불 후 정합 유지 (integrity 1.0)", rec2["integrity_rate"] == 1.0)

        # 12. MCP server
        tools = c.get("/mcp/tools").json()["tools"]
        rpc = c.post("/mcp/rpc", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                       "params": {"name": "get_customer_360", "arguments": {"customer_id": cid}}}).json()
        data = json.loads(rpc["result"]["content"][0]["text"])
        check("MCP 서버 (도구 7종 + tools/call)", len(tools) == 7 and data["customer"]["name"] == "대성정밀")

        # 13. Douzone & Google Calendar REST adapters
        import httpx
        from app.connectors.accounting import DouzoneAdapter
        from app.connectors.calendar import GoogleCalendarAdapter, ExternalEvent
        dz = DouzoneAdapter(http=httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json={"result": {"voucher_no": "DZ-001"}}))))
        dz_res = dz.post_transaction(order_id="ORD-DZ", amount=100000.0, currency="KRW")
        gc = GoogleCalendarAdapter(http=httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json={"id": "G-001", "summary": "Meeting"}))))
        gc_res = gc.upsert_event(ExternalEvent(external_id=None, title="Meeting", start="2026-08-01T10:00:00Z"))
        check("더존 · Google 캘린더 REST 어댑터", dz_res.external_id == "DZ-001" and gc_res.external_id == "G-001")

        # 14. Marketing Ads Connector
        from app.connectors.marketing_ads import build_marketing_ads_adapter
        mkt = build_marketing_ads_adapter()
        mkt_sum = mkt.get_aggregate_summary()
        check("마케팅 광고 성능 커넥터 (Aggregate Summary)", mkt_sum["active_campaigns"] >= 2 and mkt_sum["total_spend"] > 0)

    # summary
    print("\n" + "=" * 56)
    print("  Unified Ops AX — 오프라인 검증")
    print("=" * 56)
    passed = 0
    for name, ok, detail in results:
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}" + (f"  ({detail})" if detail and not ok else ""))
        passed += ok
    print("-" * 56)
    print(f"  {passed}/{len(results)} 통과")
    print("=" * 56)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    try:
        code = main()
    finally:
        try:
            os.remove(_db)
        except OSError:
            pass
    sys.exit(code)
