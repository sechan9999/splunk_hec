"""Microsoft Graph plumbing — OAuth2 client-credentials auth, paginated GET,
and binary download. httpx.Client is injectable so the connector is fully
testable offline via httpx.MockTransport."""
from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Optional

import httpx

from app.config import get_settings

_GRAPH_SCOPE = "https://graph.microsoft.com/.default"


class GraphAuthError(RuntimeError):
    pass


class GraphConfigError(RuntimeError):
    pass


class GraphAuth:
    """Acquires and caches an app-only bearer token (client credentials)."""

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        *,
        login_base_url: Optional[str] = None,
        http: Optional[httpx.Client] = None,
    ) -> None:
        self.tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret
        self._login = (login_base_url or get_settings().graph_login_url).rstrip("/")
        self._http = http or httpx.Client(timeout=30)
        self._token: Optional[str] = None
        self._expires_at = 0.0

    def token(self) -> str:
        now = time.time()
        if self._token and now < self._expires_at - 60:
            return self._token
        resp = self._http.post(
            f"{self._login}/{self.tenant_id}/oauth2/v2.0/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": _GRAPH_SCOPE,
            },
        )
        if resp.status_code != 200:
            raise GraphAuthError(f"token request failed: {resp.status_code} {resp.text}")
        data = resp.json()
        self._token = data["access_token"]
        self._expires_at = now + float(data.get("expires_in", 3600))
        return self._token


class GraphClient:
    def __init__(
        self,
        auth: GraphAuth,
        *,
        base_url: Optional[str] = None,
        http: Optional[httpx.Client] = None,
    ) -> None:
        self._auth = auth
        self._base = (base_url or get_settings().graph_base_url).rstrip("/")
        self._http = http or httpx.Client(timeout=30)

    def _url(self, path: str) -> str:
        return path if path.startswith("http") else f"{self._base}{path}"

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._auth.token()}"}

    def get_json(self, path: str, params: Optional[dict] = None) -> dict:
        resp = self._http.get(self._url(path), headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def paged(self, path: str, params: Optional[dict] = None) -> Iterator[dict]:
        url: Optional[str] = path
        while url:
            data = self.get_json(url, params)
            params = None  # nextLink already carries query state
            yield from data.get("value", [])
            url = data.get("@odata.nextLink")

    def get_bytes(self, path: str) -> bytes:
        resp = self._http.get(self._url(path), headers=self._headers())
        resp.raise_for_status()
        return resp.content

    def post_json(self, path: str, json: dict) -> dict:
        resp = self._http.post(self._url(path), headers=self._headers(), json=json)
        resp.raise_for_status()
        return resp.json()

    def patch_json(self, path: str, json: dict) -> dict:
        resp = self._http.patch(self._url(path), headers=self._headers(), json=json)
        resp.raise_for_status()
        return resp.json()

    def delete(self, path: str) -> None:
        resp = self._http.delete(self._url(path), headers=self._headers())
        resp.raise_for_status()


def build_graph_client(http: Optional[httpx.Client] = None) -> GraphClient:
    """Construct a GraphClient from settings. Raises GraphConfigError if the
    app registration credentials are missing."""
    s = get_settings()
    missing = [k for k in ("graph_tenant_id", "graph_client_id", "graph_client_secret") if not getattr(s, k)]
    if missing:
        raise GraphConfigError(f"missing Graph settings: {missing}")
    auth = GraphAuth(s.graph_tenant_id, s.graph_client_id, s.graph_client_secret,
                     login_base_url=s.graph_login_url, http=http)
    return GraphClient(auth, base_url=s.graph_base_url, http=http)
