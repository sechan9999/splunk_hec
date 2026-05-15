# 🔥 MCPAgents × Splunk — Agentic Ops Control Center

> **Splunk Agentic Ops Hackathon 2026** (May 18 – Jun 15, 2026)  
> Built on: [sechan9999/MCPagents](https://github.com/sechan9999/MCPagents) + [sechan9999/splunk-app-examples](https://github.com/sechan9999/splunk-app-examples)   https://sechan9999.github.io/splunk_hec/     

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://splunkhec.streamlit.app/)

## 🌐 Live Demo

**👉 [https://splunkhec.streamlit.app/](https://splunkhec.streamlit.app/)**

The Streamlit Cloud deployment runs in **Demo Mode** by default — all 4 tabs (Agent Run, Live Splunk Events, Auto-Remediation, DLP/SOAR) work with simulated data. Toggle Demo Mode off in the sidebar to connect to real Splunk/MCPAgents backends.

---

## 🎯 핵심 혁신: Closed-Loop Agentic Ops

MCPAgents가 **Splunk를 관찰하고(Tool)** + **Splunk가 MCPAgents를 감시(Observability)** 하는 양방향 폐쇄 루프를 구현합니다.

```
MCPAgents                    Splunk Platform
─────────────────────────────────────────────────────────
① LLM/Tool 이벤트 ──HEC──▶ Splunk Cloud (index=mcp_agents)
② Tool Manager   ◀──MCP──  Splunk MCP Server (GA 2026)
③ DLP Violation  ──WH──▶  Splunk SOAR (Foundation-sec)
④ Splunk Alert   ──WH──▶  Auto-Remediation (CDTS이상탐지)
⑤ Dashboard      ◀──SPL──  Splunk Live Panels
```

---

## 📦 프로젝트 구조

### 새로 추가된 파일

| 파일 | 주차 | 설명 |
|------|------|------|
| `splunk_telemetry.py` | Week 1 | Splunk HEC 텔레메트리 에미터 (비동기 배치) |
| `tools/splunk_mcp_tool.py` | Week 2 | Splunk MCP Server Tool connector + NL→SPL |
| `security/soar_bridge.py` | Week 3 | DLP → Foundation-sec → SOAR 자동 플레이북 |
| `security/__init__.py` | Week 3 | SOARBridge export |
| `auto_remediation.py` | Week 4 | CDTS 이상탐지 → Router 자동 복구 루프 |
| `demo_app.py` | — | Streamlit 데모 앱 (Demo Mode + 실 백엔드 지원) |
| `splunk_app/` | — | Splunk Enterprise App 패키지 (savedsearches, Modular Input) |
| `main.py` | — | FastAPI 통합 엔트리포인트 (모든 모듈 초기화) |

### 수정된 파일 (graceful degradation 패턴 — 기존 기능 100% 보장)

| 파일 | 주차 | 변경 내용 |
|------|------|----------|
| `multi_llm_platform/llm_router.py` | Week 1 | `emit_router_decision`, `emit_cache_hit/miss` 추가 |
| `multi_llm_platform/semantic_cache.py` | Week 1 | `emit_cache_hit/miss` 추가 |
| `advanced_agent.py` | Week 2·3·4 | `splunk_query` 도구 등록, DLP scan 연결, HEC 텔레메트리 훅 |
| `enterprise_mcp_connector/tool_manager.py` | Week 2 | `SplunkPlugin` 클래스 + `PLUGIN_REGISTRY["splunk"]` |

---

## 🚀 빠른 시작

### Option A: Streamlit Cloud (즉시 체험)

**[https://splunkhec.streamlit.app/](https://splunkhec.streamlit.app/)** 접속 → Demo Mode ON 상태에서 모든 기능 체험 가능.

### Option B: 로컬 실행

#### 1. 설치
```bash
pip install -r requirements-full.txt
```

#### 2. 환경 변수 설정
```bash
cp .env.example .env
# SPLUNK_HEC_URL, SPLUNK_HEC_TOKEN 설정
```

#### 3. Docker Compose (Splunk + MCPAgents + Redis)
```bash
docker-compose up
# Splunk Web:  http://localhost:8000  (admin/mcpagents2026)
# MCPAgents:   http://localhost:8001  (8001→컨테이너 내부 8000)
# Redis:       localhost:6379
```

#### 4. Streamlit 데모 앱
```bash
streamlit run demo_app.py
# → http://localhost:8501
# 사이드바에서 Demo Mode OFF → 실제 백엔드 연결
```

#### 5. 텔레메트리 테스트
```bash
python splunk_telemetry.py        # HEC 이벤트 전송 테스트
python tools/splunk_mcp_tool.py   # NL→SPL 쿼리 테스트
python security/soar_bridge.py    # DLP→SOAR 테스트
python auto_remediation.py        # 자동 복구 테스트
```

#### 6. 서버 실행 (단독 실행 — Docker 없이)
```bash
python main.py --server
# → http://localhost:8000/health
# → http://localhost:8000/docs        (Swagger UI)
# → http://localhost:8000/splunk/alert (Splunk Alert webhook)
# → http://localhost:8000/agent/run   (에이전트 API)
```

---

## 🏗️ 아키텍처

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
result = tool.execute("지난 1시간 LLM 비용 얼마야?")
# → SPL 자동 생성 + Splunk MCP Server 또는 REST API 쿼리
```

### ③ DLP → SOAR Bridge (`security/soar_bridge.py`)
```python
from security.soar_bridge import patch_dlp_engine_with_soar
from enterprise_mcp_connector.dlp_policy import DLPPolicyEngine

engine = DLPPolicyEngine()
patch_dlp_engine_with_soar(engine)
# → DLP 위반 시 Foundation-sec 스코어링 + SOAR 플레이북 자동 트리거
```

### ④ Auto-Remediation (`auto_remediation.py`)
```python
from auto_remediation import get_anomaly_handler

handler = get_anomaly_handler()
handler.handle({"result": {"anomaly_type": "cost_spike", "metric_value": "8.5"}})
# → Router cost_weight 증가 + 저비용 모델 전환
```

---

## 📊 Splunk App 설치

```bash
# Splunk Enterprise에 앱 설치
cp -r splunk_app $SPLUNK_HOME/etc/apps/mcpagents_splunk
$SPLUNK_HOME/bin/splunk restart

# HEC 토큰 생성 (Splunk Web)
# Settings → Data Inputs → HTTP Event Collector → New Token
# → index: mcp_agents, sourcetype: mcp:agent:event
```

---

## 🏆 Hackathon Tracks

| Track | 구현 |
|-------|------|
| **Observability** | HEC Telemetry + CDTS 이상탐지 + Auto-Remediation |
| **Security** | DLP → Foundation-sec → SOAR Bridge |
| **Platform** | Splunk MCP Server Tool + Modular Input + SPL NL Query |

---

## 📄 라이선스
Apache 2.0 (splunk-app-examples 동일)
