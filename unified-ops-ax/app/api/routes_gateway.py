from __future__ import annotations

from fastapi import APIRouter

from app.ai.gateway import get_gateway
from app.domain.schemas import ChatIn

router = APIRouter(prefix="/gateway", tags=["ai-gateway"])


@router.post("/chat")
def chat(body: ChatIn):
    messages = [{"role": "user", "content": body.message}]
    return get_gateway().chat(messages, provider=body.provider, model=body.model)
