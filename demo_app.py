"""
MCPAgents x Splunk — Hackathon Demo App
Streamlit all-in-one: Agent Run + Live Events + Auto-Remediation + Health
Supports DEMO MODE when backend services are unavailable (e.g. Streamlit Cloud).
"""
import json
import time
import random
import urllib3
from datetime import datetime, timedelta

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
.demo-badge {
    background: linear-gradient(135deg, #f5a623, #f7c948);
    color: #1e1e2e; padding: 4px 12px; border-radius: 12px;
    font-weight: bold; font-size: 0.75em; margin-left: 8px;
}
</style>
""", unsafe_allow_html=True)

# ── Demo data generators ─────────────────────────────────────────────────────
MODELS = ["gpt-4o", "claude-sonnet-4", "gemini-2.0-flash", "gpt-4o-mini"]

def _demo_health():
    return {
        "status": "ok", "version": "2.0.0-splunk",
        "telemetry": {"sent": random.randint(80, 350), "dropped": random.randint(0, 2)},
        "remediation": {"remediator": {"remediation_count": random.randint(3, 12),
                                        "active_cooldowns": {}}},
    }

_VISITOR_KEYWORDS = [
    "방문자", "누적 방문자", "방문자 수", "누적 방문", "방문 수",
    "visitor", "visitors", "cumulative visitor", "cumulative visitors",
    "total visitors", "visitor count", "number of visitors",
]

def _is_visitors_query(q):
    ql = (q or "").lower()
    return any(k in ql for k in _VISITOR_KEYWORDS)

def _demo_visitors(query):
    n = random.randint(5000, 50000)
    today = random.randint(40, 320)
    return {
        "success": True, "query": query,
        "result": {
            "response": (f"[Demo] Cumulative visitors: {n:,} "
                         f"(+{today} today). "
                         f"Source: Supabase visitors table (simulated)."),
            "model": "supabase-mcp",
            "tool_results": [
                {"tool": "supabase_query", "result": {
                    "source": "demo", "metric": "cumulative_visitors",
                    "count": n, "today": today, "table": "visitors"}},
            ],
        },
    }

def _demo_agent_run(query):
    if _is_visitors_query(query):
        return _demo_visitors(query)
    model = random.choice(MODELS)
    return {
        "success": True, "query": query,
        "result": {
            "response": f"[Demo] Analysis complete for '{query}'. Total cost $4.23 in the last hour, avg latency 320ms, 2 DLP violations detected.",
            "model": model, "latency_ms": random.randint(180, 900),
            "cost_usd": round(random.uniform(0.01, 0.15), 4),
            "tool_results": [
                {"tool": "splunk_query", "result": {"spl": "index=mcp_agents | stats count by model", "rows": 5}},
                {"tool": "cost_analyzer", "result": {"total_cost": 4.23, "top_model": model}},
            ],
        },
    }

def _demo_events(n=8):
    rows = []
    now = datetime.now()
    etypes = ["mcp_llm_call", "mcp_router_decision", "mcp_tool_call", "mcp_cache_hit", "mcp_dlp_violation"]
    for i in range(n):
        t = now - timedelta(seconds=random.randint(10, 600))
        rows.append({
            "_time": t.strftime("%Y-%m-%dT%H:%M:%S"),
            "event_type": random.choice(etypes),
            "model": random.choice(MODELS),
            "cost_usd": str(round(random.uniform(0.001, 0.12), 4)),
            "latency_ms": str(random.randint(80, 1200)),
        })
    return sorted(rows, key=lambda r: r["_time"], reverse=True)

def _demo_alert(anomaly_type, value):
    thresholds = {"cost_spike": 5.0, "latency_spike": 3000, "error_rate_high": 0.15,
                  "dlp_burst": 10, "token_overrun": 100000}
    th = thresholds.get(anomaly_type, 5.0)
    return {
        "handled": True, "anomaly_type": anomaly_type,
        "anomaly_value": float(value), "threshold": th,
        "actions": [
            {"action": "downgrade_model", "result": "gpt-4o → gpt-4o-mini"},
            {"action": "enable_cache", "result": "semantic_cache=ON"},
            {"action": "rate_limit", "result": "max_rpm=30"},
            {"action": "emit_telemetry", "result": "HEC event sent"},
        ],
        "cooldown_sec": 600,
    }

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Configuration")
    demo_mode = st.toggle("🎮 Demo Mode", value=True,
                          help="Run with simulated data. Turn off to connect to real backends.")
    st.divider()
    if demo_mode:
        st.caption("🎮 Demo Mode — backend & credentials not used (simulated data).")
        mcpagents_url = "http://localhost:8001"
        splunk_rest   = "https://localhost:8089"
        splunk_user   = ""
        splunk_pass   = ""
        hec_url       = "http://localhost:8088"
        hec_token     = ""
        splunk_index  = "mcp_agents"
    else:
        mcpagents_url = st.text_input("MCPAgents URL", "http://localhost:8001")
        splunk_rest   = st.text_input("Splunk REST URL", "https://localhost:8089")
        splunk_user   = st.text_input("Splunk User", "")
        splunk_pass   = st.text_input("Splunk Password", "", type="password")
        hec_url       = st.text_input("HEC URL", "http://localhost:8088")
        hec_token     = st.text_input("HEC Token", "", type="password")
        splunk_index  = st.text_input("Splunk Index", "mcp_agents")
    st.divider()
    auto_refresh  = st.toggle("Auto-refresh (5s)", value=False)

# ── Helpers ───────────────────────────────────────────────────────────────────
def _get(url, **kw):
    try:
        return requests.get(url, timeout=5, **kw)
    except Exception:
        return None

def _post(url, **kw):
    try:
        return requests.post(url, timeout=30, **kw)
    except Exception:
        return None

def health():
    if demo_mode:
        return _demo_health()
    r = _get(f"{mcpagents_url}/health")
    return r.json() if r and r.ok else None

def agent_run(query, user_id="demo"):
    if demo_mode:
        time.sleep(0.5)
        return _demo_agent_run(query)
    r = _post(f"{mcpagents_url}/agent/run", json={"query": query, "user_id": user_id})
    return r.json() if r and r.ok else {"error": str(r)}

def fire_alert(anomaly_type, value):
    if demo_mode:
        time.sleep(0.3)
        return _demo_alert(anomaly_type, value)
    r = _post(f"{mcpagents_url}/splunk/alert",
              json={"result": {"anomaly_type": anomaly_type, "metric_value": str(value)}})
    return r.json() if r and r.ok else {"error": "connection failed"}

def splunk_search(spl, earliest="-15m", limit=20):
    if demo_mode:
        return _demo_events(random.randint(5, 12))
    try:
        r = requests.post(
            f"{splunk_rest}/services/search/jobs/export",
            auth=(splunk_user, splunk_pass),
            data={"search": f"search index={splunk_index} {spl} | head {limit}",
                  "output_mode": "json", "earliest_time": earliest},
            verify=False, timeout=10,
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
    except Exception:
        return []

def hec_status():
    if demo_mode:
        return True
    try:
        r = requests.get(f"{hec_url}/services/collector/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False

# ── Header ────────────────────────────────────────────────────────────────────
title_col, badge_col = st.columns([6, 1])
with title_col:
    st.title("🔥 MCPAgents × Splunk — Agentic Ops Control Center")
with badge_col:
    if demo_mode:
        st.markdown('<span class="demo-badge">🎮 DEMO</span>', unsafe_allow_html=True)
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
        st.metric("HEC Sent", tel.get("sent", 0), f"dropped={tel.get('dropped', 0)}")
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
    "🤖 Agent Run", "📊 Live Splunk Events", "🔧 Auto-Remediation", "🛡️ DLP / SOAR",
])

# ── Tab 1: Agent Run ──────────────────────────────────────────────────────────
with tab_agent:
    st.subheader("Run MCPAgents Query")
    col_q, col_u = st.columns([4, 1])
    with col_q:
        query = st.text_input("Query", placeholder="e.g. What was the LLM cost in the last hour?",
                              label_visibility="collapsed")
    with col_u:
        user_id = st.text_input("User ID", "demo", label_visibility="collapsed")

    if st.button("▶ Run Agent", type="primary", use_container_width=True):
        if not query:
            st.warning("Please enter a query.")
        else:
            with st.spinner("Running agent..."):
                t0 = time.time()
                result = agent_run(query, user_id)
                elapsed = time.time() - t0

            failed = result.get("success") is False or (
                "error" in result and not result.get("success"))
            if failed:
                st.error(f"Error: {result}")
            else:
                st.success(f"Complete — {elapsed:.2f}s")
                res_obj = result.get("result", {})
                # Show response text
                if isinstance(res_obj, dict) and res_obj.get("response"):
                    st.info(res_obj["response"])
                # Tool results
                steps = res_obj.get("tool_results", []) if isinstance(res_obj, dict) else []
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
                with st.expander("📄 Raw response"):
                    st.json(result)

    st.divider()
    st.markdown("**Quick Prompts**")
    quick = [
        "LLM cost in the last hour?",
        "Show recent DLP violations",
        "Model with highest error rate today?",
        "Cache hit rate statistics",
        "Number of cumulative visitors",
    ]
    cols = st.columns(len(quick))
    for i, q in enumerate(quick):
        if cols[i].button(q, key=f"quick_{i}", use_container_width=True):
            with st.spinner("Running..."):
                r = agent_run(q, "demo")
            res_obj = r.get("result", {})
            if isinstance(res_obj, dict) and res_obj.get("response"):
                st.info(res_obj["response"])
            steps = res_obj.get("tool_results", []) if isinstance(res_obj, dict) else []
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
            with st.expander("📄 Raw response"):
                st.json(r)

# ── Tab 2: Live Splunk Events ─────────────────────────────────────────────────
with tab_events:
    st.subheader("Live Events — index=mcp_agents")

    col_f, col_t, col_btn = st.columns([2, 1, 1])
    with col_f:
        spl_filter = st.text_input("SPL filter",
                                   "| fields event_type,model,cost_usd,latency_ms,_time",
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
            st.info("No events — check Splunk connection or verify data exists.")
        else:
            st.success(f"{len(rows)} events")
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
    st.markdown("**Example SPL Queries**")
    spl_examples = {
        "Cost Summary": "| stats sum(cost_usd) as total_cost by model",
        "DLP Violations": "event_type=mcp_dlp_violation | table _time,rule_id,sensitivity,action_taken",
        "Anomaly Detection": "event_type=mcp_anomaly | table _time,anomaly_type,metric_value",
        "Router Decisions": "event_type=mcp_router_decision | table _time,query_complexity,selected_model",
    }
    for label, spl in spl_examples.items():
        if st.button(label, key=f"spl_{label}"):
            with st.spinner("Querying..."):
                rows = splunk_search(spl, earliest="-1h", limit=10)
            if rows:
                st.dataframe(rows, use_container_width=True)
            else:
                st.info("No results")

# ── Tab 3: Auto-Remediation ───────────────────────────────────────────────────
with tab_remediation:
    st.subheader("Auto-Remediation Simulator")
    st.caption("Splunk CDTS Anomaly Alert → MCPAgents /splunk/alert → Auto-Remediation")

    scenarios = {
        "💸 Cost Spike": ("cost_spike", 9.2),
        "🐢 Latency Spike": ("latency_spike", 6500),
        "❌ Error Rate High": ("error_rate_high", 0.25),
        "🚨 DLP Burst": ("dlp_burst", 20),
        "📝 Token Overrun": ("token_overrun", 150000),
    }

    st.markdown("#### Select Scenario")
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

    any_result = False
    for label, (atype, _) in scenarios.items():
        key = f"last_alert_{atype}"
        if key in st.session_state:
            any_result = True
            resp = st.session_state[key]
            handled = resp.get("handled", False)
            skipped = resp.get("skipped", False)
            icon = "✅" if handled else ("⏭️" if skipped else "⚠️")
            with st.expander(f"{icon} {label} — Result", expanded=True):
                if handled:
                    st.success(f"handled=True | anomaly_value={resp.get('anomaly_value')} ≥ threshold={resp.get('threshold')}")
                    actions = resp.get("actions", [])
                    for act in actions:
                        st.markdown(f"- **{act['action']}**: `{act['result']}`")
                    st.caption(f"cooldown={resp.get('cooldown_sec')}s")
                elif skipped:
                    st.info(f"⏭️ Skipped (cooldown) — {resp.get('reason', 'cooldown active')}")
                elif resp.get("error"):
                    st.error(f"Connection failed — {resp.get('error')}")
                else:
                    st.warning(f"Not handled — {resp.get('reason', resp)}")

    if not any_result:
        st.info("Click a scenario button above to simulate an anomaly.")

    st.divider()
    st.markdown("#### Custom Alert")
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
    st.caption("Text Input → DLP Scan → SOAR Playbook Auto-Trigger")

    test_text = st.text_area(
        "Text to scan for PII",
        value="Customer: John Doe, SSN: 123-45-6789, Card: 4111-1111-1111-1111",
        height=100,
    )

    if st.button("🛡️ DLP Scan + SOAR", type="primary"):
        with st.spinner("Scanning..."):
            resp = agent_run(f"analyze this text for PII: {test_text[:200]}", "soar-demo")

        st.markdown("**Scan Result**")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Agent Response**")
            res_obj = resp.get("result", {})
            if isinstance(res_obj, dict) and res_obj.get("response"):
                st.info(res_obj["response"])
            steps = res_obj.get("tool_results", []) if isinstance(res_obj, dict) else []
            if steps:
                for s in steps:
                    st.markdown(f"- `{s.get('tool')}`: {str(s.get('result',''))[:200]}")
            else:
                st.json(resp)

        with col_b:
            st.markdown("**SOAR Playbooks** _(triggered on DLP violation)_")
            playbooks = [
                ("mcp_block_user", "Block high-risk user"),
                ("mcp_notify_security", "Notify security team"),
                ("mcp_quarantine_session", "Quarantine session"),
                ("mcp_enrich_ioc", "IOC enrichment & analysis"),
            ]
            for pb, desc in playbooks:
                st.markdown(f"- **`{pb}`**: {desc}")

    st.divider()
    st.markdown("#### Foundation-sec Risk Scoring")
    st.caption("Splunk Foundation-sec hosted model scores PII sensitivity")

    col1, col2, col3, col4 = st.columns(4)
    risk_examples = [
        ("SSN Detected", "HIGH", "#f38ba8"),
        ("Card Number", "HIGH", "#f38ba8"),
        ("Email Only", "MEDIUM", "#fab387"),
        ("Plain Text", "LOW", "#a6e3a1"),
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
