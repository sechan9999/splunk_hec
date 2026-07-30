"""SharePoint connector tests. Real Graph HTTP paths are exercised via
httpx.MockTransport (no live tenant), with focus on the security-critical
permission -> ACL mapping and the end-to-end trim into retrieval."""
import httpx
import pytest

from app.connectors.graph_client import GraphAuth, GraphClient
from app.connectors.sharepoint import NO_ACCESS, SharePointConnector, map_permissions
from app.rag.ingest import ingest_document
from app.rag.service import retrieve


# --- permission mapping (unit) ----------------------------------------------
def test_map_user_and_group_grants():
    perms = [
        {"grantedToV2": {"user": {"id": "U1"}}},
        {"grantedToV2": {"group": {"id": "G1"}}},
    ]
    assert map_permissions(perms) == ["grp:G1", "usr:U1"]


def test_map_org_link_to_grp_all():
    assert map_permissions([{"link": {"scope": "organization"}}]) == ["grp:all"]


def test_map_anonymous_link_is_public():
    assert map_permissions([{"link": {"scope": "anonymous"}}]) == []


def test_map_empty_is_fail_closed():
    assert map_permissions([]) == [NO_ACCESS]


def test_map_legacy_and_identities_lists():
    perms = [
        {"grantedTo": {"user": {"id": "Uold"}}},
        {"grantedToIdentitiesV2": [{"group": {"id": "Gx"}}, {"siteGroup": {"id": "7"}}]},
    ]
    assert map_permissions(perms) == ["grp:Gx", "sgrp:7", "usr:Uold"]


# --- Graph HTTP paths via MockTransport -------------------------------------
def _make_client(counter):
    def handler(request: httpx.Request) -> httpx.Response:
        host, path = request.url.host, request.url.path
        if host == "login.microsoftonline.com":
            counter["token"] += 1
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        routes = {
            "/v1.0/sites/site1/drives": {"value": [{"id": "drv1", "name": "Documents"}]},
            "/v1.0/drives/drv1/items/root/children": {"value": [
                {"id": "fld1", "name": "Policies", "folder": {"childCount": 1}},
                {"id": "itmA", "name": "handbook.md", "file": {"mimeType": "text/markdown"},
                 "size": 40, "webUrl": "https://sp/A"},
            ]},
            "/v1.0/drives/drv1/items/fld1/children": {"value": [
                {"id": "itmB", "name": "salary.md", "file": {}, "size": 40, "webUrl": "https://sp/B"},
                {"id": "itmC", "name": "diagram.png", "file": {}, "size": 99, "webUrl": "https://sp/C"},
            ]},
            "/v1.0/drives/drv1/items/itmA/permissions": {"value": [{"link": {"scope": "organization"}}]},
            "/v1.0/drives/drv1/items/itmB/permissions": {"value": [{"grantedToV2": {"group": {"id": "HR"}}}]},
        }
        if path in routes:
            return httpx.Response(200, json=routes[path])
        if path == "/v1.0/drives/drv1/items/itmA/content":
            return httpx.Response(200, content=b"company handbook vacation policy onboarding general")
        if path == "/v1.0/drives/drv1/items/itmB/content":
            return httpx.Response(200, content=b"confidential salary payroll ledger withholding deductions")
        return httpx.Response(404, json={"error": {"code": "notFound", "message": path}})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    auth = GraphAuth("tenant1", "cid", "secret", login_base_url="https://login.microsoftonline.com", http=http)
    return GraphClient(auth, base_url="https://graph.microsoft.com/v1.0", http=http)


def test_connector_enumerates_and_mirrors_acls():
    counter = {"token": 0}
    conn = SharePointConnector(_make_client(counter), "site1")
    docs = {d.title: d for d in conn.list_documents()}

    # recursion found both text files; binary (.png) skipped
    assert set(docs) == {"handbook.md", "salary.md"}
    assert docs["handbook.md"].acl == ["grp:all"]      # org-wide link
    assert docs["salary.md"].acl == ["grp:HR"]         # group grant mirrored
    assert docs["salary.md"].external_id == "itmB"
    assert counter["token"] == 1                        # token cached across all calls


def test_sharepoint_acls_drive_security_trimming(session):
    conn = SharePointConnector(_make_client({"token": 0}), "site1")
    for src in conn.list_documents():
        ingest_document(session, title=src.title, content=src.content, acl=src.acl,
                        source="sharepoint", external_id=src.external_id)
    session.commit()

    # A user without grp:HR cannot retrieve the salary doc, even on-topic
    outsider = ["grp:all", "grp:sales"]
    titles = {h.meta["title"] for h in retrieve("salary payroll ledger withholding", outsider, k=5)}
    assert "salary.md" not in titles
    assert "handbook.md" in titles  # grp:all visible to everyone

    # An HR member does retrieve it
    hr = ["grp:all", "grp:HR"]
    hr_titles = {h.meta["title"] for h in retrieve("salary payroll ledger", hr, k=5)}
    assert "salary.md" in hr_titles


def test_permissions_failure_is_fail_closed():
    """If the permissions call errors, the item must be locked, not public."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "login.microsoftonline.com":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        path = request.url.path
        if path == "/v1.0/sites/site1/drives":
            return httpx.Response(200, json={"value": [{"id": "drv1"}]})
        if path == "/v1.0/drives/drv1/items/root/children":
            return httpx.Response(200, json={"value": [
                {"id": "itmX", "name": "x.md", "file": {}, "size": 5}]})
        if path == "/v1.0/drives/drv1/items/itmX/content":
            return httpx.Response(200, content=b"some text")
        if path.endswith("/permissions"):
            return httpx.Response(500, json={"error": "boom"})  # permissions unreadable
        return httpx.Response(404, json={})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    auth = GraphAuth("t", "c", "s", login_base_url="https://login.microsoftonline.com", http=http)
    conn = SharePointConnector(GraphClient(auth, base_url="https://graph.microsoft.com/v1.0", http=http), "site1")
    docs = conn.list_documents()
    assert docs[0].acl == [NO_ACCESS]
