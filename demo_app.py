"""
MCPAgents x Splunk — Hackathon Demo App
Streamlit all-in-one: Agent Run + Live Events + Auto-Remediation + Health
"""
import json
import time
import urllib3
from datetime import datetime

import requests
import streamlit as st

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MCPAgents x Splunk",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.metric-card {
    background: #1e1e2e; border-radius: 8px; padding: 16px;
    border: 1px solid #313244; margin: 4px 0;
}
.status-ok  { color: #a6e3a1; font-weight: bold; }
.status-err { color: #f38ba8; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Configuration")
    mcpagents_url = st.text_input("MCPAgents URL", "http://localhost:8001")
    splunk_rest   = st.text_input("Splunk REST URL", "https://localhost:8089")
    splunk_user   = st.text_input("Splunk User", "admin")
    splunk_pass   = st.text_input("Splunk Password", "mcpagents2026", type="password")
    hec_url       = st.text_input("HEC URL", "http://localhost:8088")
    hec_token     = st.text_input("HEC Token", "", type="password")
    splunk_index  = st.text_input("Splunk Index", "mcp_agents")
    st.divider()
    auto_refresh  = st.toggle("Auto-refresh (5s)", value=False)

# ── Helpers ───────────────────────────────────────────────────────────────────
def _get(url, **kw):
    try:
        return requests.get(url, timeout=5, **kw)
    except Exception as e:
        return None

def _post(url, **kw):
    try:
        return requests.post(url, timeout=30, **kw)
    except Exception as e:
        return None

def health():
    r = _get(f"{mcpagents_url}/health")
    return r.json() if r and r.ok else None

def agent_run(query, user_id="demo"):
    r = _post(f"{mcpagents_url}/agent/run",
              json={"query": query, "user_id": user_id})
    return r.json() if r and r.ok else {"error": str(r)}

def fire_alert(anomaly_type, value):
    r = _post(f"{mcpagents_url}/splunk/alert",
              json={"result": {"anomaly_type": anomaly_type,
                               "metric_value": str(value)}})
    return r.json() if r and r.ok else {"error": "connection failed"}

def splunk_search(spl, earliest="-15m", limit=20):
    try:
        r = requests.post(
            f"{splunk_rest}/services/search/jobs/export",
            auth=(splunk_user, splunk_pass),
            data={
                "search": f"search index={splunk_index} {spl} | head {limit}",
                "output_mode": "json",
                "earliest_time": earliest,
            },
            verify=False,
            timeout=10,
        )
        rows = []
        for line in r.text.strip().splitlines():
            if not line:
                continue
            try:
                d = json.loads(line)
                if "result" in d:
                    rows.append(d["result"])
            except Exception:
                pass
        return rows
    except Exception as e:
        return []

def hec_status():
    try:
        r = requests.get(f"{hec_url}/services/collector/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🔥 MCPAgents × Splunk — Agentic Ops Control Center")
st.caption("Splunk Agentic Ops Hackathon 2026 | Observability · Security · Platform")

# ── Quick health bar ──────────────────────────────────────────────────────────
h = health()
col1, col2, col3, col4 = st.columns(4)

with col1:
    if h:
        st.metric("MCPAgents", "🟢 Healthy", f"v{h.get('version','?')}")
    else:
        st.metric("MCPAgents", "🔴 Offline", "check URL")

with col2:
    hec_ok = hec_status()
    st.metric("Splunk HEC", "🟢 Ready" if hec_ok else "🔴 Offline",
              hec_url.replace("http://", ""))

with col3:
    if h:
        tel = h.get("telemetry", {})
        st.metric("HEC Sent", tel.get("sent", 0),
                  f"dropped={tel.get('dropped', 0)}")
    else:
        st.metric("HEC Sent", "—")

with col4:
    if h:
        rem = h.get("remediation", {}).get("remediator", {})
        st.metric("Remediations", rem.get("remediation_count", 0),
                  f"cooldowns={len(rem.get('active_cooldowns', {}))}")
    else:
        st.metric("Remediations", "—")

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_agent, tab_events, tab_remediation, tab_soar = st.tabs([
    "🤖 Agent Run",
    "📊 Live Splunk Events",
    "🔧 Auto-Remediation",
    "🛡️ DLP / SOAR",
])

# ── Tab 1: Agent Run ──────────────────────────────────────────────────────────
with tab_agent:
    st.subheader("Run MCPAgents Query")
    col_q, col_u = st.columns([4, 1])
    with col_q:
        query = st.text_input("Query", placeholder="e.g. 지난 1시간 LLM 비용 얼마야?",
                              label_visibility="collapsed")
    with col_u:
        user_id = st.text_input("User ID", "demo", label_visibility="collapsed")

    if st.button("▶ Run Agent", type="primary", use_container_width=True):
        if not query:
            st.warning("쿼리를 입력하세요.")
        else:
            with st.spinner("Running agent..."):
                t0 = time.time()
                result = agent_run(query, user_id)
                elapsed = time.time() - t0

            if "error" in result and not result.get("success"):
                st.error(f"Error: {result}")
            else:
                st.success(f"완료 — {elapsed:.2f}s")

                # Tool results
                steps = result.get("steps", []) or result.get("result", {}).get("tool_results", [])
                if steps:
                    st.markdown("**Tool Calls**")
                    for step in steps:
                        tool = step.get("tool", step.get("tool_name", "?"))
                        res  = step.get("result", step.get("output", ""))
                        with st.expander(f"🔧 `{tool}`"):
                            if isinstance(res, dict):
                                st.json(res)
                            else:
                                st.code(str(res)[:2000], language="text")

                # Raw response
                with st.expander("📄 Raw response"):
                    st.json(result)

    st.divider()
    st.markdown("**Quick prompts**")
    quick = [
        "지난 1시간 LLM 비용 얼마야?",
        "최근 DLP 위반 목록 보여줘",
        "오늘 에러율이 가장 높은 모델은?",
        "캐시 히트율 통계 알려줘",
    ]
    cols = st.columns(len(quick))
    for i, q in enumerate(quick):
        if cols[i].button(q, key=f"quick_{i}", use_container_width=True):
            with st.spinner("Running..."):
                r = agent_run(q, "demo")
            st.json(r)

# ── Tab 2: Live Splunk Events ─────────────────────────────────────────────────
with tab_events:
    st.subheader("Live Events — index=mcp_agents")

    col_f, col_t, col_btn = st.columns([2, 1, 1])
    with col_f:
        spl_filter = st.text_input("SPL filter", "| fields event_type,model,cost_usd,latency_ms,_time",
                                   label_visibility="collapsed")
    with col_t:
        earliest = st.selectbox("Range", ["-5m", "-15m", "-1h", "-24h"],
                                label_visibility="collapsed")
    with col_btn:
        fetch = st.button("🔄 Fetch", use_container_width=True)

    if fetch or auto_refresh:
        with st.spinner("Querying Splunk..."):
            rows = splunk_search(spl_filter, earliest=earliest)

        if not rows:
            st.info("이벤트 없음 — Splunk에 데이터가 없거나 연결을 확인하세요.")
        else:
            st.success(f"{len(rows)}개 이벤트")
            # Clean up display fields
            display = []
            for r in rows:
                display.append({
                    "time":       r.get("_time", ""),
                    "event_type": r.get("event_type", ""),
                    "model":      r.get("model", ""),
                    "cost_usd":   r.get("cost_usd", ""),
                    "latency_ms": r.get("latency_ms", ""),
                })
            st.dataframe(display, use_container_width=True)

            with st.expander("Raw JSON"):
                st.json(rows[:5])

    st.divider()
    st.markdown("**SPL 예시 쿼리**")
    spl_examples = {
        "비용 집계": "| stats sum(cost_usd) as total_cost by model",
        "DLP 위반": "event_type=mcp_dlp_violation | table _time,rule_id,sensitivity,action_taken",
        "이상탐지": "event_type=mcp_anomaly | table _time,anomaly_type,metric_value",
        "라우터 결정": "event_type=mcp_router_decision | table _time,query_complexity,selected_model",
    }
    for label, spl in spl_examples.items():
        if st.button(label, key=f"spl_{label}"):
            with st.spinner("Querying..."):
                rows = splunk_search(spl, earliest="-1h", limit=10)
            if rows:
                st.dataframe(rows, use_container_width=True)
            else:
                st.info("결과 없음")

# ── Tab 3: Auto-Remediation ───────────────────────────────────────────────────
with tab_remediation:
    st.subheader("Auto-Remediation Simulator")
    st.caption("Splunk CDTS 이상탐지 Alert → MCPAgents /splunk/alert → 자동 복구")

    scenarios = {
        "💸 Cost Spike": ("cost_spike", 9.2),
        "🐢 Latency Spike": ("latency_spike", 6500),
        "❌ Error Rate High": ("error_rate_high", 0.25),
        "🚨 DLP Burst": ("dlp_burst", 20),
        "📝 Token Overrun": ("token_overrun", 150000),
    }

    st.markdown("#### 시나리오 선택")
    cols = st.columns(len(scenarios))
    for i, (label, (atype, val)) in enumerate(scenarios.items()):
        with cols[i]:
            st.markdown(f"**{label}**")
            st.caption(f"`{atype}` = {val:,}")
            if st.button("Fire Alert", key=f"alert_{atype}", use_container_width=True):
                with st.spinner("Sending alert..."):
                    resp = fire_alert(atype, val)
                st.session_state[f"last_alert_{atype}"] = resp

    st.divider()

    # Show results for fired alerts
    any_result = False
    for label, (atype, _) in scenarios.items():
        key = f"last_alert_{atype}"
        if key in st.session_state:
            any_result = True
            resp = st.session_state[key]
            handled = resp.get("handled", False)
            with st.expander(f"{'✅' if handled else '⚠️'} {label} — 결과", expanded=True):
                if handled:
                    st.success(f"handled=True | anomaly_value={resp.get('anomaly_value')} ≥ threshold={resp.get('threshold')}")
                    actions = resp.get("actions", [])
                    for act in actions:
                        st.markdown(f"- **{act['action']}**: `{act['result']}`")
                    st.caption(f"cooldown={resp.get('cooldown_sec')}s")
                else:
                    st.warning(f"handled=False — {resp}")

    if not any_result:
        st.info("위 버튼을 눌러 이상 시나리오를 시뮬레이션하세요.")

    st.divider()
    st.markdown("#### 커스텀 Alert")
    col_type, col_val, col_fire = st.columns([2, 1, 1])
    with col_type:
        custom_type = st.selectbox("Anomaly Type",
            ["cost_spike", "latency_spike", "error_rate_high", "dlp_burst", "token_overrun"],
            label_visibility="collapsed")
    with col_val:
        custom_val = st.number_input("Value", value=10.0, label_visibility="collapsed")
    with col_fire:
        if st.button("🔥 Fire", use_container_width=True, type="primary"):
            with st.spinner("Firing..."):
                resp = fire_alert(custom_type, custom_val)
            st.json(resp)

# ── Tab 4: DLP / SOAR ────────────────────────────────────────────────────────
with tab_soar:
    st.subheader("DLP → Foundation-sec → SOAR Pipeline")
    st.caption("텍스트 입력 → DLP 스캔 → SOAR 플레이북 자동 트리거 (시뮬레이션)")

    test_text = st.text_area(
        "DLP 스캔할 텍스트",
        value="고객 이름: 홍길동, 주민번호: 900101-1234567, 카드번호: 4111-1111-1111-1111",
        height=100,
    )

    if st.button("🛡️ DLP Scan + SOAR", type="primary"):
        # We call agent/run with the text to trigger DLP scan via AdvancedMCPAgent
        with st.spinner("Scanning..."):
            resp = agent_run(f"analyze this text for PII: {test_text[:200]}", "soar-demo")

        st.markdown("**Scan Result**")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Agent Response**")
            steps = resp.get("result", {}).get("tool_results", [])
            if steps:
                for s in steps:
                    st.markdown(f"- `{s.get('tool')}`: {str(s.get('result',''))[:200]}")
            else:
                st.json(resp)

        with col_b:
            st.markdown("**SOAR Playbooks** _(if DLP triggered)_")
            playbooks = [
                ("mcp_block_user", "HIGH 위험 사용자 차단"),
                ("mcp_notify_security", "보안팀 알림"),
                ("mcp_quarantine_session", "세션 격리"),
                ("mcp_enrich_ioc", "IOC 분석"),
            ]
            for pb, desc in playbooks:
                st.markdown(f"- **`{pb}`**: {desc}")

    st.divider()
    st.markdown("#### Foundation-sec Risk Scoring")
    st.caption("Splunk Foundation-sec 호스팅 모델이 PII 민감도를 점수화합니다")

    col1, col2, col3, col4 = st.columns(4)
    risk_examples = [
        ("SSN 포함", "HIGH", "#f38ba8"),
        ("카드번호 포함", "HIGH", "#f38ba8"),
        ("이메일만", "MEDIUM", "#fab387"),
        ("일반 텍스트", "LOW", "#a6e3a1"),
    ]
    for (label, level, color), col in zip(risk_examples, [col1, col2, col3, col4]):
        with col:
            st.markdown(f"""
            <div class="metric-card" style="border-color:{color}">
                <div style="color:{color};font-size:0.8em">{label}</div>
                <div style="font-size:1.5em;font-weight:bold;color:{color}">{level}</div>
            </div>
            """, unsafe_allow_html=True)

# ── Auto-refresh ──────────────────────────────────────────────────────────────
if auto_refresh:
    time.sleep(5)
    st.rerun()
