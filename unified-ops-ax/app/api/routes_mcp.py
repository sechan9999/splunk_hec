from __future__ import annotations

from fastapi import APIRouter

from app.db import SessionLocal
from app.mcp.registry import TOOLS
from app.mcp.server import handle_request

router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.get("/tools")
def list_tools():
    """Discovery mirror of the MCP tools/list."""
    return {"tools": [t.public() for t in TOOLS]}


@router.post("/rpc")
def rpc(message: dict):
    """HTTP bridge for the JSON-RPC MCP handler (stdio is the canonical channel)."""
    return handle_request(message, SessionLocal)
