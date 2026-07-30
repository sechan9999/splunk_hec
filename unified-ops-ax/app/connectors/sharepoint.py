"""SharePoint / Teams connector over Microsoft Graph.

Security model: each item's Graph permissions are mirrored to ACL principals
so the platform's security trimming stays faithful to the source. Mapping is
**fail-closed** — if permissions cannot be read, the document is locked to a
sentinel nobody holds, never left public.

Graph app registration needs (application permissions, admin-consented):
  Sites.Read.All, Files.Read.All, Group.Read.All.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator

from app.config import get_settings
from app.connectors.base import SourceDocument
from app.connectors.extract import extract_text, is_extractable
from app.connectors.graph_client import GraphAuth, GraphClient, GraphConfigError

# ACL sentinel assigned when permissions are unknown/unreadable. No role's
# principals contain it, so the doc is invisible until permissions resolve.
NO_ACCESS = "grp:__no_access__"


def map_permissions(permissions: Iterable[dict]) -> list[str]:
    """Map Graph permission objects to ACL principals.

    - user grant       -> usr:<id>
    - group grant      -> grp:<id>
    - SharePoint group -> sgrp:<id>
    - org-wide link    -> grp:all  (everyone in tenant; RBAC gives all roles grp:all)
    - anonymous link   -> [] (truly public)
    - nothing readable -> [NO_ACCESS] (fail closed)
    """
    principals: set[str] = set()
    public = False

    for perm in permissions:
        link = perm.get("link") or {}
        scope = link.get("scope")
        if scope == "anonymous":
            public = True
        elif scope == "organization":
            principals.add("grp:all")

        identities: list[dict] = []
        for key in ("grantedToV2", "grantedTo"):
            val = perm.get(key)
            if val:
                identities.append(val)
        for key in ("grantedToIdentitiesV2", "grantedToIdentities"):
            val = perm.get(key)
            if val:
                identities.extend(val)

        for ident in identities:
            for field, prefix in (("user", "usr"), ("group", "grp"), ("siteGroup", "sgrp")):
                obj = ident.get(field)
                if obj and obj.get("id"):
                    principals.add(f"{prefix}:{obj['id']}")

    if public:
        return []
    if principals:
        return sorted(principals)
    return [NO_ACCESS]


class _GraphDriveConnector:
    """Shared crawl logic for any Graph drive (SharePoint doc lib or Teams files)."""

    source = "graph"

    def __init__(self, client: GraphClient) -> None:
        self.client = client

    def _walk(self, drive_id: str, item_id: str = "root") -> Iterator[tuple[str, dict]]:
        for child in self.client.paged(f"/drives/{drive_id}/items/{item_id}/children"):
            # Graph marks item kind by facet-key presence; the facet can be {}.
            if "folder" in child:
                yield from self._walk(drive_id, child["id"])
            elif "file" in child:
                yield drive_id, child

    def _permissions(self, drive_id: str, item_id: str) -> list[str]:
        try:
            perms = list(self.client.paged(f"/drives/{drive_id}/items/{item_id}/permissions"))
        except Exception:
            return [NO_ACCESS]  # fail closed
        return map_permissions(perms)

    def _to_document(self, drive_id: str, item: dict) -> SourceDocument | None:
        name = item.get("name", "")
        if not is_extractable(name):
            return None  # skip binaries without downloading (see extract.py hook)
        content = self.client.get_bytes(f"/drives/{drive_id}/items/{item['id']}/content")
        text = extract_text(name, content)
        if text is None:
            return None
        acl = self._permissions(drive_id, item["id"])
        return SourceDocument(
            external_id=item["id"],
            title=name,
            content=text,
            acl=acl,
            uri=item.get("webUrl"),
            meta={"drive_id": drive_id, "size": item.get("size"), "source": self.source},
        )

    def _crawl(self, drive_ids: Iterable[str]) -> list[SourceDocument]:
        docs: list[SourceDocument] = []
        for drive_id in drive_ids:
            for did, item in self._walk(drive_id):
                doc = self._to_document(did, item)
                if doc:
                    docs.append(doc)
        return docs


class SharePointConnector(_GraphDriveConnector):
    source = "sharepoint"

    def __init__(self, client: GraphClient, site_id: str) -> None:
        super().__init__(client)
        self.site_id = site_id

    def list_documents(self) -> list[SourceDocument]:
        drive_ids = [d["id"] for d in self.client.paged(f"/sites/{self.site_id}/drives")]
        return self._crawl(drive_ids)


class TeamsConnector(_GraphDriveConnector):
    """A Team's files live in the group's default drive — same Graph plumbing."""

    source = "teams"

    def __init__(self, client: GraphClient, group_id: str) -> None:
        super().__init__(client)
        self.group_id = group_id

    def list_documents(self) -> list[SourceDocument]:
        drive_id = self.client.get_json(f"/groups/{self.group_id}/drive")["id"]
        return self._crawl([drive_id])


def _build_client(http=None) -> GraphClient:
    s = get_settings()
    missing = [
        k for k in ("graph_tenant_id", "graph_client_id", "graph_client_secret")
        if not getattr(s, k)
    ]
    if missing:
        raise GraphConfigError(f"missing Graph settings: {missing}")
    auth = GraphAuth(
        s.graph_tenant_id, s.graph_client_id, s.graph_client_secret,
        login_base_url=s.graph_login_url, http=http,
    )
    return GraphClient(auth, base_url=s.graph_base_url, http=http)


def build_sharepoint_connector(http=None) -> SharePointConnector:
    s = get_settings()
    if not s.sharepoint_site_id:
        raise GraphConfigError("missing Graph settings: ['sharepoint_site_id']")
    return SharePointConnector(_build_client(http), s.sharepoint_site_id)


def build_teams_connector(http=None) -> TeamsConnector:
    s = get_settings()
    if not s.teams_group_id:
        raise GraphConfigError("missing Graph settings: ['teams_group_id']")
    return TeamsConnector(_build_client(http), s.teams_group_id)
