"""MCP server — JSON-RPC protocol conformance (offline, no SDK)."""
import json

from app.db import SessionLocal
from app.domain.models import Customer
from app.mcp.server import handle_request


def _req(method, params=None, mid=1):
    return {"jsonrpc": "2.0", "id": mid, "method": method, "params": params or {}}


def test_initialize():
    r = handle_request(_req("initialize"), SessionLocal)
    assert r["result"]["protocolVersion"] == "2024-11-05"
    assert r["result"]["serverInfo"]["name"] == "unified-ops-ax"
    assert "tools" in r["result"]["capabilities"]


def test_tools_list_advertises_hub_tools():
    r = handle_request(_req("tools/list"), SessionLocal)
    names = {t["name"] for t in r["result"]["tools"]}
    assert {"search_knowledge", "get_customer_360", "reconcile_accounting", "triage_ticket"} <= names
    # every tool advertises an input schema
    assert all("inputSchema" in t for t in r["result"]["tools"])


def test_tools_call_get_customer_360(session):
    cust = Customer(name="Acme", segment="B2B")
    session.add(cust)
    session.commit()
    r = handle_request(_req("tools/call", {"name": "get_customer_360", "arguments": {"customer_id": cust.id}}), SessionLocal)
    data = json.loads(r["result"]["content"][0]["text"])
    assert data["customer"]["name"] == "Acme"
    assert "timeline" in data


def test_tools_call_unknown_tool_is_error():
    r = handle_request(_req("tools/call", {"name": "nope", "arguments": {}}), SessionLocal)
    assert r["error"]["code"] == -32602


def test_tools_call_reports_handler_error_in_band(session):
    # get_customer_360 with a bad id returns an in-band error payload, not a crash
    r = handle_request(_req("tools/call", {"name": "get_customer_360", "arguments": {"customer_id": "missing"}}), SessionLocal)
    data = json.loads(r["result"]["content"][0]["text"])
    assert data.get("error")  # "customer not found"


def test_method_not_found():
    r = handle_request(_req("does/notexist"), SessionLocal)
    assert r["error"]["code"] == -32601


def test_notification_gets_no_response():
    assert handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"}, SessionLocal) is None


def test_search_knowledge_tool(session):
    from app.rag.ingest import ingest_document
    ingest_document(session, title="Return Policy", content="returns within 30 days with receipt", acl=[])
    session.commit()
    r = handle_request(_req("tools/call", {"name": "search_knowledge", "arguments": {"query": "return window", "role": "sales"}}), SessionLocal)
    data = json.loads(r["result"]["content"][0]["text"])
    assert data["citations"] and data["citations"][0]["title"] == "Return Policy"
