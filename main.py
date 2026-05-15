# main.py
"""
MCPAgents × Splunk — Unified Entry Point
Splunk 통합 버전 메인 애플리케이션

모든 통합 모듈을 초기화하고 FastAPI 서버를 실행합니다.
"""

import os
import logging
import asyncio
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)


def initialize_splunk_integration():
    """Splunk 통합 초기화"""
    from splunk_telemetry import init_telemetry
    from security.soar_bridge import get_soar_bridge
    from tools.splunk_mcp_tool import SplunkMCPTool
    from auto_remediation import get_anomaly_handler

    # ① HEC Telemetry
    hec_url   = os.environ.get("SPLUNK_HEC_URL", "")
    hec_token = os.environ.get("SPLUNK_HEC_TOKEN", "")
    tel = init_telemetry(hec_url, hec_token)
    logger.info(f"① Splunk HEC Telemetry: {'enabled' if hec_token else 'local-only'}")

    # ② Splunk MCP Tool
    splunk_tool = SplunkMCPTool()
    logger.info(f"② Splunk MCP Tool: {'MCP Server' if splunk_tool._mcp_available else 'REST API fallback'}")

    # ③ SOAR Bridge
    bridge = get_soar_bridge()
    logger.info(f"③ Splunk SOAR Bridge: {'enabled' if bridge.enabled else 'disabled (no token)'}")

    # ④ Auto-Remediation Handler
    handler = get_anomaly_handler()
    logger.info(f"④ Auto-Remediation: ready ({len(handler._policies)} policies)")

    # DLP Engine에 SOAR 패치
    try:
        from enterprise_mcp_connector.dlp_policy import DLPPolicyEngine
        from security.soar_bridge import patch_dlp_engine_with_soar
        dlp = DLPPolicyEngine()
        patch_dlp_engine_with_soar(dlp, bridge)
        logger.info("  DLP → SOAR patch applied")
    except Exception as e:
        logger.warning(f"  DLP patch skipped: {e}")

    return tel, splunk_tool, bridge, handler


def create_app():
    """FastAPI 앱 생성"""
    try:
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        from auto_remediation import get_anomaly_handler, create_splunk_webhook_router

        app = FastAPI(
            title="MCPAgents × Splunk",
            description="Enterprise AI Control Center with Splunk Agentic Ops",
            version="2.0.0-splunk",
        )
        app.add_middleware(CORSMiddleware, allow_origins=["*"],
                           allow_methods=["*"], allow_headers=["*"])

        handler = get_anomaly_handler()

        # ── Splunk webhook 라우터 ──────────────────────────
        splunk_router = create_splunk_webhook_router(handler)
        if splunk_router:
            app.include_router(splunk_router)

        # ── Metrics API (Splunk Modular Input 폴링용) ──────
        @app.get("/metrics/llm")
        async def metrics_llm():
            from multi_llm_platform.observability import Tracer, DebugDashboard
            db = DebugDashboard(Tracer())
            return db.get_statistics()

        @app.get("/metrics/cost")
        async def metrics_cost():
            from splunk_telemetry import get_telemetry
            return get_telemetry().get_stats()

        @app.get("/metrics/dlp")
        async def metrics_dlp():
            from enterprise_mcp_connector.dlp_policy import DLPPolicyEngine
            return DLPPolicyEngine().get_statistics()

        @app.get("/metrics/router")
        async def metrics_router():
            return {"status": "ok", "message": "router metrics via HEC telemetry"}

        @app.get("/metrics/cache")
        async def metrics_cache():
            return {"status": "ok", "message": "cache metrics via HEC telemetry"}

        @app.get("/health")
        async def health():
            from splunk_telemetry import get_telemetry
            return {
                "status":    "ok",
                "version":   "2.0.0-splunk",
                "telemetry": get_telemetry().get_stats(),
                "remediation": get_anomaly_handler().stats(),
            }

        # ── Agent 실행 엔드포인트 ──────────────────────────
        @app.post("/agent/run")
        async def run_agent(body: dict):
            from advanced_agent import AdvancedMCPAgent, AgentContext
            from splunk_telemetry import get_telemetry
            import time

            query      = body.get("query", "")
            user_id    = body.get("user_id", "anonymous")
            session_id = body.get("session_id", f"web_{int(time.time())}")

            tel = get_telemetry()
            tel.set_session(session_id, user_id)
            tel.emit_agent_start(query)

            agent = AdvancedMCPAgent()
            ctx   = AgentContext(session_id=session_id, user_id=user_id, query=query)
            resp  = await agent.execute(query, ctx)

            tel.emit_agent_complete(
                query=query, total_steps=len(resp.steps),
                duration_ms=resp.duration_ms, total_cost=resp.cost,
                total_tokens=resp.tokens_used, success=resp.success,
                error=str(resp.result.get("error","")) if not resp.success else ""
            )
            return {"success": resp.success, "result": resp.result,
                    "steps": len(resp.steps), "duration_ms": resp.duration_ms}

        logger.info("✅ FastAPI app created")
        return app

    except ImportError as e:
        logger.error(f"FastAPI not available: {e}. Install: pip install fastapi uvicorn")
        return None


if __name__ == "__main__":
    import sys

    logger.info("=" * 60)
    logger.info("🚀 MCPAgents × Splunk — Starting Up")
    logger.info("=" * 60)

    # Splunk 통합 초기화
    initialize_splunk_integration()

    # 서버 모드
    if "--server" in sys.argv:
        try:
            import uvicorn
            app = create_app()
            if app:
                port = int(os.environ.get("MCPAGENTS_WEBHOOK_PORT", 8000))
                logger.info(f"🌐 Server: http://localhost:{port}")
                uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
        except ImportError:
            logger.error("uvicorn not installed. Run: pip install uvicorn")
    else:
        # 데모 모드: 에이전트 실행 + 텔레메트리 검증
        logger.info("Running in demo mode (use --server for HTTP server)")

        async def demo():
            from advanced_agent import AdvancedMCPAgent
            from splunk_telemetry import get_telemetry

            tel = get_telemetry()
            tel.set_session("demo-001", "gyver")

            agent = AdvancedMCPAgent()
            queries = [
                "React hooks 사용법과 예제 코드를 알려줘",
                "pandas로 데이터 분석하는 코드 작성해줘",
            ]
            for q in queries:
                tel.emit_agent_start(q)
                resp = await agent.execute(q)
                tel.emit_agent_complete(q, total_steps=len(resp.steps),
                                        duration_ms=resp.duration_ms, success=resp.success)
                logger.info(f"✅ [{q[:30]}...] success={resp.success}")

            tel.flush()
            logger.info(f"📊 HEC Stats: {tel.get_stats()}")

        asyncio.run(demo())
