from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import (
    routes_agents,
    routes_gateway,
    routes_governance,
    routes_hub,
    routes_mcp,
    routes_ops,
    routes_rag,
    routes_views,
    routes_workspace,
)
from app.config import get_settings
from app.db import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    worker = None
    if settings.event_worker_enabled:
        from app.worker import get_worker

        worker = get_worker()
        worker.start()
    yield
    if worker:
        worker.stop()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "llm_provider": settings.default_llm_provider,
        "embedding_provider": settings.embedding_provider,
        "vector_backend": settings.vector_backend,
    }


app.include_router(routes_hub.router)
app.include_router(routes_rag.router)
app.include_router(routes_gateway.router)
app.include_router(routes_ops.router)
app.include_router(routes_agents.router)
app.include_router(routes_views.router)
app.include_router(routes_workspace.router)
app.include_router(routes_governance.router)
app.include_router(routes_mcp.router)
