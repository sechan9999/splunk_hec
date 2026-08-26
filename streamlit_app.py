"""Unified Ops AX — Streamlit Control Center Dashboard.

Interactive web interface for Fleet Controls, PyDeck 3D Spatial Maps, K8s Pod Scaling,
and Local DLP Guardrails.
"""

import asyncio
import os
import threading
import time

import pandas as pd
import pydeck as pdk
import streamlit as st

from async_agent_engine import AsyncAgentEngine, TaskPriority
from auto_remediation import AnomalyType

# Page Configuration
st.set_page_config(
    page_title="Unified Ops AX — Fleet Control Center",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Dark Mode Glassmorphism Theme CSS
st.markdown("""
<style>
    .stApp {
        background-color: #0e1117;
        color: #e0e0e0;
    }
    .metric-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 16px;
        backdrop-filter: blur(10px);
    }
    .badge-success {
        background-color: #059669;
        color: #ecfdf5;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-warning {
        background-color: #d97706;
        color: #fffbeb;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-danger {
        background-color: #dc2626;
        color: #fef2f2;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)


# Persistent Process-Wide Async Engine with Daemon Thread Loop
@st.cache_resource
def get_engine() -> AsyncAgentEngine:
    eng = AsyncAgentEngine(num_workers=4)
    loop = asyncio.new_event_loop()
    threading.Thread(target=loop.run_forever, daemon=True).start()
    asyncio.run_coroutine_threadsafe(eng.start(), loop).result()
    eng._loop = loop
    return eng


engine: AsyncAgentEngine = get_engine()


def call_coro(coro, timeout: float = 10.0):
    """Safely executes a coroutine on the process-wide daemon event loop."""
    future = asyncio.run_coroutine_threadsafe(coro, engine._loop)
    return future.result(timeout=timeout)


# Sidebar Navigation
st.sidebar.image("https://img.icons8.com/isometric/96/server.png", width=70)
st.sidebar.title("Unified Ops AX")
st.sidebar.markdown("**AI Fleet Control Desk**")
st.sidebar.markdown("---")

nav_choice = st.sidebar.radio(
    "Navigation",
    ["🌐 Global 3D Fleet Map", "⚡ Async Engine & Workers", "☸️ K8s HPA Pod Scaling", "🔒 Local DLP Guardrail", "📜 Telemetry & Policy Logs"]
)

# Header Section
st.title("🚀 Unified Ops AX: Fleet Control Center")
st.caption("Autonomous Background Multi-Agent Telemetry & Self-Healing Remediation Engine (Google ADK & Gemini 3.5 Flash)")

# -----------------------------------------------------------------------------
# TAB 1: Global 3D Fleet Map
# -----------------------------------------------------------------------------
if nav_choice == "🌐 Global 3D Fleet Map":
    st.subheader("🌐 Global Multi-Region Telemetry Fleet Map")
    st.markdown("Real-time 3D spatial mapping of telemetry ingest streams across Google Cloud regions (`us-central1`, `europe-west1`, `asia-east1`).")

    status = engine.get_status()
    
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    col_m1.metric("Active Regions", "3 Monitored", delta="us-central1, eu-west1, asia-east1")
    col_m2.metric("Queue Throughput", f"{status['throughput_tasks_per_sec']} tasks/s", delta=f"{status['active_workers']}/4 Active Workers")
    col_m3.metric("K8s Replicas", f"{status['k8s_autoscaling']['current_replicas']} pods", delta=status['k8s_autoscaling']['mode_badge'])
    col_m4.metric("Total Tasks Processed", f"{status['total_processed']} tasks", delta=f"{round(status['total_processed'] * 0.51, 1)} KB Telemetry")

    # PyDeck 3D Map Data
    tp = status['throughput_tasks_per_sec']
    nodes_df = pd.DataFrame([
        {"name": "GCP us-central1 (Iowa)", "lat": 41.2619, "lon": -95.8608, "workers": status['active_workers'], "throughput": tp, "color": [255, 99, 71, 220]},
        {"name": "GCP europe-west1 (Belgium)", "lat": 50.4542, "lon": 3.8258, "workers": status['active_workers'], "throughput": tp, "color": [0, 255, 128, 220]},
        {"name": "GCP asia-east1 (Taiwan)", "lat": 24.0175, "lon": 120.5050, "workers": status['active_workers'], "throughput": tp, "color": [0, 128, 255, 220]}
    ])

    arcs_df = pd.DataFrame([
        {"from_lat": 41.2619, "from_lon": -95.8608, "to_lat": 50.4542, "to_lon": 3.8258},
        {"from_lat": 41.2619, "from_lon": -95.8608, "to_lat": 24.0175, "to_lon": 120.5050}
    ])

    view_state = pdk.ViewState(
        latitude=30.0,
        longitude=0.0,
        zoom=1.4,
        pitch=45,
        bearing=0
    )

    nodes_layer = pdk.Layer(
        "ScatterplotLayer",
        data=nodes_df,
        get_position=["lon", "lat"],
        get_color="color",
        get_radius=250000,
        pickable=True
    )

    arcs_layer = pdk.Layer(
        "ArcLayer",
        data=arcs_df,
        get_source_position=["from_lon", "from_lat"],
        get_target_position=["to_lon", "to_lat"],
        get_source_color=[0, 255, 128],
        get_target_color=[0, 128, 255],
        get_width=4
    )

    r = pdk.Deck(
        layers=[nodes_layer, arcs_layer],
        initial_view_state=view_state,
        tooltip={"text": "{name}\nActive Workers: {workers}\nThroughput: {throughput} tasks/s"}
    )

    st.pydeck_chart(r)

# -----------------------------------------------------------------------------
# TAB 2: Async Engine & Workers
# -----------------------------------------------------------------------------
elif nav_choice == "⚡ Async Engine & Workers":
    st.subheader("⚡ AsyncAgentEngine Worker Status & Queue Controls")
    
    status = engine.get_status()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Engine State", "RUNNING" if status["is_running"] else "DEGRADED", delta=f"{status['active_workers']} active workers")
    col2.metric("Worker Count", f"{status['num_workers']} Threads")
    col3.metric("Processed Tasks", f"{status['total_processed']} Tasks", delta=f"{status['throughput_tasks_per_sec']} tasks/sec")

    st.markdown("### Interactive Task Submission & Anomaly Simulation")
    
    sim_col1, sim_col2 = st.columns(2)
    
    with sim_col1:
        st.markdown("#### Submit Background Batch Job")
        log_count = st.slider("Log Event Volume per Batch", 100, 2000, 500, step=100)
        task_priority = st.selectbox("Priority", ["NORMAL", "HIGH", "CRITICAL", "LOW"])
        
        if st.button("Enqueue Batch Ingest Job", use_container_width=True):
            p_map = {"NORMAL": TaskPriority.NORMAL, "HIGH": TaskPriority.HIGH, "CRITICAL": TaskPriority.CRITICAL, "LOW": TaskPriority.LOW}
            
            def dummy_job():
                time.sleep(0.01)
                return f"Processed batch of {log_count} log events"
                
            task = call_coro(engine.submit_task(dummy_job, name=f"user_batch_{log_count}", priority=p_map[task_priority]))
            st.success(f"Enqueued Task ID: `{task.task_id[:16]}` (Priority: {task_priority})")
            st.rerun()

    with sim_col2:
        st.markdown("#### Simulate Splunk Anomaly Alert")
        anomaly_sel = st.selectbox("Anomaly Type", ["COST_SPIKE", "LATENCY_SPIKE", "DLP_BURST"])
        metric_val = st.number_input("Metric Value", value=8.5, min_value=1.0, max_value=10000.0)
        
        if st.button("Trigger Auto-Remediation Policy", use_container_width=True):
            a_map = {"COST_SPIKE": AnomalyType.COST_SPIKE, "LATENCY_SPIKE": AnomalyType.LATENCY_SPIKE, "DLP_BURST": AnomalyType.DLP_BURST}
            res = call_coro(engine.trigger_anomaly_remediation(a_map[anomaly_sel], metric_val))
            st.warning(f"Policy Executed: `{res.get('status', 'remediated')}`")
            st.json(res)
            st.rerun()

    st.markdown("### Current Queue Counts")
    st.json(status["counts"])

# -----------------------------------------------------------------------------
# TAB 3: K8s HPA Pod Scaling
# -----------------------------------------------------------------------------
elif nav_choice == "☸️ K8s HPA Pod Scaling":
    st.subheader("☸️ Kubernetes Horizontal Pod Autoscaler (HPA)")
    st.markdown("Dynamic pod replica scaling of deployment `unified-ops-agent-pool` upon latency spike detection.")

    k8s_stats = engine.k8s_autoscaler.get_stats()
    
    kc1, kc2, kc3, kc4 = st.columns(4)
    kc1.metric("Deployment Name", k8s_stats["deployment_name"])
    kc2.metric("Namespace", k8s_stats["namespace"])
    kc3.metric("Current Pod Replicas", f"{k8s_stats['current_replicas']} Pods", delta=k8s_stats["mode_badge"])
    kc4.metric("Scaling Events", f"{k8s_stats['total_scaling_events']} Events")

    st.markdown(f"### Scale Deployment Replicas ({k8s_stats['mode_badge']})")
    target_pods = st.slider("Target Pod Replicas", k8s_stats["min_replicas"], k8s_stats["max_replicas"], k8s_stats["current_replicas"])
    
    if st.button("Apply kubectl scale deployment"):
        res = call_coro(engine.k8s_autoscaler.scale_deployment_async(target_pods, reason="manual_user_override"))
        st.success(f"Scaling result: {res}")
        st.rerun()

    st.markdown("### Pod Scaling History")
    if k8s_stats["last_event"]:
        st.json(k8s_stats["last_event"])
    else:
        st.info("No scaling events recorded yet.")

# -----------------------------------------------------------------------------
# TAB 4: Local DLP Guardrail
# -----------------------------------------------------------------------------
elif nav_choice == "🔒 Local DLP Guardrail":
    st.subheader("🔒 Fine-Tuned Local DLP Guardrail & PII Masking")
    st.markdown("Zero-latency offline classification and sanitization of sensitive PII (SSN, KR_RRN, Credit Cards with Luhn validation, API Keys, Email, Phone) before telemetry emission.")

    dlp_stats = engine.dlp_guardrail.get_stats()
    
    dc1, dc2, dc3 = st.columns(3)
    dc1.metric("Total Inspections", f"{dlp_stats['total_inspections']} Payloads")
    dc2.metric("Rule Violations", f"{dlp_stats['total_violations']} Blocked")
    dc3.metric("Clean Rate", f"{dlp_stats['clean_rate_pct']}%")

    st.markdown("### Live DLP Payload Inspection Playground")
    sample_payload = st.text_area(
        "Payload Content for Inspection",
        value="User query from SSN 123-45-6789 (KR_RRN 900101-1234567) with card 4532 0151 1283 0366 and API key sk-proj-abcdef12345678901234567890."
    )
    
    if st.button("Inspect & Mask PII Payload"):
        res = engine.dlp_guardrail.inspect_and_mask(sample_payload)
        st.markdown(f"**Clean Status**: `{'CLEAN' if res.is_clean else 'VIOLATION'}` | **Sensitivity**: `{res.sensitivity}` | **HMAC Data Hash**: `{res.data_hash}`")
        st.markdown("**Matched Rules**:")
        st.write(res.matched_rules if res.matched_rules else "None")
        st.markdown("**Masked Output Payload**:")
        st.code(res.masked_text)

# -----------------------------------------------------------------------------
# TAB 5: Telemetry & Policy Logs
# -----------------------------------------------------------------------------
elif nav_choice == "📜 Telemetry & Policy Logs":
    st.subheader("📜 Prometheus Metric Stream & System Logs")
    st.markdown("Real-time Prometheus text exposition endpoint `/metrics` for Grafana dashboard scraping.")

    status = engine.get_status()
    
    metrics_payload = f"""# HELP async_engine_processed_tasks_total Total tasks processed by engine
# TYPE async_engine_processed_tasks_total counter
async_engine_processed_tasks_total{{status="completed"}} {status['total_processed']}

# HELP async_engine_throughput_tasks_per_sec Current task throughput rate
# TYPE async_engine_throughput_tasks_per_sec gauge
async_engine_throughput_tasks_per_sec {status['throughput_tasks_per_sec']}

# HELP k8s_pod_replicas_current Current deployment worker pod count
# TYPE k8s_pod_replicas_current gauge
k8s_pod_replicas_current{{deployment="{status['k8s_autoscaling']['deployment_name']}"}} {status['k8s_autoscaling']['current_replicas']}

# HELP dlp_rule_violations_total Total DLP security rule violations
# TYPE dlp_rule_violations_total counter
dlp_rule_violations_total {status['local_dlp']['total_violations']}
"""
    st.code(metrics_payload, language="promql")
