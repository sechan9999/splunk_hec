"""MCP server — Model Context Protocol over JSON-RPC 2.0. Implements the core
methods (initialize, tools/list, tools/call) without an SDK dependency, so it
is fully testable offline. Run over stdio for an MCP client:

    python -m app.mcp.server

`handle_request` is pure (message -> response dict) and drives both the stdio
loop and the HTTP `/mcp/rpc` bridge."""
from __future__ import annotations

import json

from app.mcp.registry import TOOLS, TOOLS_BY_NAME

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "unified-ops-ax", "version": "0.1.0"}


def _ok(mid, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _err(mid, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def handle_request(message: dict, session_factory) -> dict | None:
    method = message.get("method")
    mid = message.get("id")
    params = message.get("params") or {}

    if method == "initialize":
        return _ok(mid, {"protocolVersion": PROTOCOL_VERSION,
                         "capabilities": {"tools": {}}, "serverInfo": SERVER_INFO})

    if method == "tools/list":
        return _ok(mid, {"tools": [t.public() for t in TOOLS]})

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        tool = TOOLS_BY_NAME.get(name)
        if tool is None:
            return _err(mid, -32602, f"unknown tool: {name}")
        session = session_factory()
        try:
            result = tool.handler(session, args)
            text = json.dumps(result, ensure_ascii=False, default=str)
            return _ok(mid, {"content": [{"type": "text", "text": text}]})
        except Exception as exc:  # tool errors are reported in-band per MCP
            return _ok(mid, {"content": [{"type": "text", "text": str(exc)}], "isError": True})
        finally:
            session.close()

    if method is not None and method.startswith("notifications/"):
        return None  # notifications get no response

    return _err(mid, -32601, f"method not found: {method}")


def serve_stdio() -> None:  # pragma: no cover - I/O loop
    import sys

    from app.db import SessionLocal, init_db

    init_db()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = handle_request(message, SessionLocal)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":  # pragma: no cover
    serve_stdio()
