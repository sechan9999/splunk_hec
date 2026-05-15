# 🔥 MCPAgents × Splunk — Agentic Ops Control Center

> **Splunk Agentic Ops Hackathon 2026** (May 18 – Jun 15, 2026)  
> Built on: [sechan9999/MCPagents](https://github.com/sechan9999/MCPagents) + [sechan9999/splunk-app-examples](https://github.com/sechan9999/splunk-app-examples)

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://splunkhec.streamlit.app/)

## 🌐 Live Demo

**👉 [https://splunkhec.streamlit.app/](https://splunkhec.streamlit.app/)**

The Streamlit Cloud deployment runs in **Demo Mode** by default — all 4 tabs (Agent Run, Live Splunk Events, Auto-Remediation, DLP/SOAR) work with simulated data. Toggle Demo Mode off in the sidebar to connect to real Splunk/MCPAgents backends.

---

## 🎯 Core Innovation: Closed-Loop Agentic Ops

MCPAgents **observes Splunk (Tool)** + **Splunk monitors MCPAgents (Observability)** — a bidirectional closed loop:

```
MCPAgents                    Splunk Platform
─────────────────────────────────────────────────────────
① LLM/Tool events ──HEC──▶  Splunk Cloud (index=mcp_agents)
② Tool Manager    ◀──MCP──  Splunk MCP Server (GA 2026)
③ DLP Violation   ──WH──▶   Splunk SOAR (Foundation-sec)
④ Splunk Alert    ──WH──▶   Auto-Remediation (CDTS anomaly)
⑤ Dashboard       ◀──SPL──  Splunk Live Panels
```

---

## 📦 Project Structure

### New Files

| File | Week | Description |
|------|------|-------------|
| `splunk_telemetry.py` | Week 1 | Async batch HEC telemetry emitter with retry logic |
| `tools/splunk_mcp_tool.py` | Week 2 | Splunk MCP Server Tool connector + NL→SPL translation |
| `security/soar_bridge.py` | Week 3 | DLP → Foundation-sec scoring → SOAR playbook automation |
| `security/__init__.py` | Week 3 | SOARBridge export |
| `auto_remediation.py` | Week 4 | CDTS anomaly detection → Router auto-remediation loop |
| `demo_app.py` | — | Streamlit demo app (Demo Mode + live backend support) |
| `splunk_app/` | — | Splunk Enterprise App package (saved searches, Modular Input) |
| `main.py` | — | FastAPI unified entry point (all modules initialized) |

### Modified Files (Graceful Degradation — original functionality 100% preserved)

| File | Week | Changes |
|------|------|---------|
| `multi_llm_platform/llm_router.py` | Week 1 | Added `emit_router_decision`, `emit_cache_hit/miss` hooks |
| `multi_llm_platform/semantic_cache.py` | Week 1 | Added `emit_cache_hit/miss` hooks |
| `advanced_agent.py` | Week 2–4 | Registered `splunk_query` tool, DLP scan integration, HEC telemetry hooks |
| `enterprise_mcp_connector/tool_manager.py` | Week 2 | Added `SplunkPlugin` class + `PLUGIN_REGISTRY["splunk"]` |

---

## 🚀 Quick Start

### Option A: Streamlit Cloud (Instant Demo)

Visit **[https://splunkhec.streamlit.app/](https://splunkhec.streamlit.app/)** — Demo Mode is on by default. No setup required.

### Option B: Local Development

#### 1. Install Dependencies
```bash
pip install -r requirements-full.txt
```

#### 2. Configure Environment
```bash
cp .env.example .env
# Set SPLUNK_HEC_URL and SPLUNK_HEC_TOKEN
```

#### 3. Docker Compose (Splunk + MCPAgents + Redis)
```bash
docker-compose up
# Splunk Web:  http://localhost:8000  (admin/mcpagents2026)
# MCPAgents:   http://localhost:8001
# Redis:       localhost:6379
```

#### 4. Run Streamlit Demo App
```bash
streamlit run demo_app.py
# → http://localhost:8501
# Toggle Demo Mode OFF in sidebar to connect to live backends
```

#### 5. Component Tests
```bash
python splunk_telemetry.py        # HEC event emission test
python tools/splunk_mcp_tool.py   # NL→SPL query test
python security/soar_bridge.py    # DLP→SOAR pipeline test
python auto_remediation.py        # Auto-remediation test
```

#### 6. Standalone Server (without Docker)
```bash
python main.py --server
# → http://localhost:8000/health
# → http://localhost:8000/docs        (Swagger UI)
# → http://localhost:8000/splunk/alert (Splunk Alert webhook)
# → http://localhost:8000/agent/run   (Agent API)
```

---

## 🏗️ Architecture

### ① Splunk HEC Telemetry Emitter (`splunk_telemetry.py`)
```python
from splunk_telemetry import get_telemetry, init_telemetry

tel = init_telemetry(hec_url, hec_token)
tel.emit_llm_call(model="claude-sonnet-4", cost_usd=0.003, latency_ms=780)
tel.emit_router_decision(complexity="COMPLEX", selected_model="claude-sonnet-4")
tel.emit_dlp_violation(rule_id="DLP-001", action_taken="block")
```

### ② Splunk MCP Tool (`tools/splunk_mcp_tool.py`)
```python
from tools.splunk_mcp_tool import SplunkMCPTool

tool = SplunkMCPTool()
result = tool.execute("What was the LLM cost in the last hour?")
# → Auto-generates SPL + queries via Splunk MCP Server or REST API
```

### ③ DLP → SOAR Bridge (`security/soar_bridge.py`)
```python
from security.soar_bridge import patch_dlp_engine_with_soar
from enterprise_mcp_connector.dlp_policy import DLPPolicyEngine

engine = DLPPolicyEngine()
patch_dlp_engine_with_soar(engine)
# → On DLP violation: Foundation-sec risk scoring + SOAR playbook trigger
```

### ④ Auto-Remediation (`auto_remediation.py`)
```python
from auto_remediation import get_anomaly_handler

handler = get_anomaly_handler()
handler.handle({"result": {"anomaly_type": "cost_spike", "metric_value": "8.5"}})
# → Increases Router cost_weight + switches to lower-cost model
```

---

## 📊 Splunk App Installation

```bash
# Install the app on Splunk Enterprise
cp -r splunk_app $SPLUNK_HOME/etc/apps/mcpagents_splunk
$SPLUNK_HOME/bin/splunk restart

# Create HEC Token (via Splunk Web)
# Settings → Data Inputs → HTTP Event Collector → New Token
# → index: mcp_agents, sourcetype: mcp:agent:event
```

---

## 🏆 Hackathon Tracks

| Track | Implementation |
|-------|---------------|
| **Observability** | HEC Telemetry + CDTS anomaly detection + Auto-Remediation loop |
| **Security** | DLP → Foundation-sec scoring → SOAR playbook automation |
| **Platform** | Splunk MCP Server Tool + Modular Input + SPL natural language query |

---

## 📄 License
Apache 2.0 (same as splunk-app-examples)
