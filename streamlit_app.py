"""Unified Ops AX — Enterprise Streamlit Control Center & Spatial Dashboard

Built for All Things Agentic Hackathon on Devpost.
Features:
- PyDeck 3D Spatial Fleet Flow Map (us-central1, europe-west1, asia-east1).
- AsyncAgentEngine Real-Time Metrics & Worker Status.
- Kubernetes HPA Pod Replica Autoscaler Control.
- Offline Fine-Tuned DLP Guardrail & PII Masking Simulator.
- Real-Time Event-Driven Auto-Remediation Policy Monitor.
"""

import asyncio
import time
import pandas as pd
import pydeck as pdk
import streamlit as st

from async_agent_engine import AsyncAgentEngine, TaskPriority, TaskStatus
from auto_remediation import AnomalyType
from local_dlp_guardrail import LocalDLPGuardrail
from pubsub_kafka_stream_processor import StreamMessage

# Page Configuration
st.set_page_config(
    page_title="Unified Ops AX — Fleet Control Center",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Dark Theme Custom Styling
st.markdown("""
<style>
    .stApp {
        background-color: #0b0f19;
        color: #e2e8f0;
    }
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
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

# Initialize Session State Engine
if "engine" not in st.session_state:
    engine = AsyncAgentEngine(num_workers=4)
    asyncio.run(engine.start())
    st.session_state.engine = engine

engine: AsyncAgentEngine = st.session_state.engine

# Sidebar Navigation
st.sidebar.image("https://img.icons8.com/isometric/96/server.png", width=70)
st.sidebar.title("Unified Ops AX")
st.sidebar.markdown("**AI Fleet Control Desk**")
st.sidebar.markdown("---")

nav_choice = st.sidebar.radio(
    "Navigation",
    ["🌐 Global 3D Fleet Map", "⚡ Async Engine & Workers", "☸️ K8s HPA Pod Scaling", "🔒 Local DLP Guardrail", "📜 Telemetry & Policy Logs"]
)

st.sidebar.markdown("---")
st.sidebar.markdown("### Hackathon Context")
st.sidebar.info("**All Things Agentic Hackathon**\n\nGoogle Cloud + Gemini 3.5 Flash\nCategory: Fortified Enterprise Fleet")

# Header Section
st.title("🚀 Unified Ops AX: Fleet Control Center")
st.caption("Autonomous Background Multi-Agent Telemetry & Self-Healing Remediation Engine")

# -----------------------------------------------------------------------------
# TAB 1: Global 3D Fleet Map
# -----------------------------------------------------------------------------
if nav_choice == "🌐 Global 3D Fleet Map":
    st.subheader("🌐 Global Multi-Region Telemetry Fleet Map")
    st.markdown("Real-time 3D spatial mapping of telemetry ingest streams across Google Cloud regions (`us-central1`, `europe-west1`, `asia-east1`).")

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    status = engine.get_status()
    
    col_m1.metric("Active Regions", "3 Monitored", delta="us-central1, eu-west1, asia-east1")
    col_m2.metric("Queue Throughput", f"{status['throughput_tasks_per_sec']} tasks/s", delta="Async Worker Pool")
    col_m3.metric("K8s Replicas", f"{status['k8s_autoscaling']['current_replicas']} pods", delta="HPA Active")
    col_m4.metric("Total Logs Ingested", "2,000 events", delta="1.02 MB")

    # PyDeck 3D Map Data
    nodes_df = pd.DataFrame([
        {"name": "GCP us-central1 (Iowa)", "lat": 41.2619, "lon": -95.8608, "workers": 4, "throughput": 38.7, "color": [255, 99, 71, 220]},
        {"name": "GCP europe-west1 (Belgium)", "lat": 50.4542, "lon": 3.8258, "workers": 4, "throughput": 35.2, "color": [0, 255, 128, 220]},
        {"name": "GCP asia-east1 (Taiwan)", "lat": 24.0175, "lon": 120.5050, "workers": 4, "throughput": 31.5, "color": [0, 128, 255, 220]}
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
    col1.metric("Engine State", "RUNNING" if status["is_running"] else "STOPPED")
    col2.metric("Worker Count", f"{status['num_workers']} Threads")
    col3.metric("Processed Tasks", f"{status['total_processed']} Tasks")

    st.markdown("### Interactive Task Submission & Anomaly Simulation")
    
    sim_col1, sim_col2 = st.columns(2)
    
    with sim_col1:
        st.markdown("#### Submit Background Batch Job")
        log_count = st.slider("Log Event Volume per Batch", 100, 2000, 500, step=100)
        task_priority = st.selectbox("Priority", ["NORMAL", "HIGH", "CRITICAL", "LOW"])
        
        if st.button("Enqueue Batch Ingest Job", use_container_width=True):
            p_map = {"NORMAL": TaskPriority.NORMAL, "HIGH": TaskPriority.HIGH, "CRITICAL": TaskPriority.CRITICAL, "LOW": TaskPriority.LOW}
            
            def dummy_job():
                time.sleep(0.02)
                return f"Processed batch of {log_count} log events"
                
            task = asyncio.run(engine.submit_task(dummy_job, name=f"user_batch_{log_count}", priority=p_map[task_priority]))
            st.success(f"Enqueued Task ID: `{task.task_id[:16]}` (Priority: {task_priority})")

    with sim_col2:
        st.markdown("#### Simulate Splunk Anomaly Alert")
        anomaly_sel = st.selectbox("Anomaly Type", ["COST_SPIKE", "LATENCY_SPIKE", "DLP_BURST"])
        metric_val = st.number_input("Metric Value", value=8.5, min_value=1.0, max_value=10000.0)
        
        if st.button("Trigger Auto-Remediation Policy", use_container_width=True):
            a_map = {"COST_SPIKE": AnomalyType.COST_SPIKE, "LATENCY_SPIKE": AnomalyType.LATENCY_SPIKE, "DLP_BURST": AnomalyType.DLP_BURST}
            res = asyncio.run(engine.trigger_anomaly_remediation(a_map[anomaly_sel], metric_val))
            st.warning(f"Policy Executed: `{res.get('status', 'remediated')}`")
            st.json(res)

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
    kc3.metric("Current Pod Replicas", f"{k8s_stats['current_replicas']} Pods", delta=f"Min: {k8s_stats['min_replicas']} / Max: {k8s_stats['max_replicas']}")
    kc4.metric("Scaling Events", f"{k8s_stats['total_scaling_events']} Events")

    st.markdown("### Scale Deployment Replicas Manually")
    target_pods = st.slider("Target Pod Replicas", k8s_stats["min_replicas"], k8s_stats["max_replicas"], k8s_stats["current_replicas"])
    
    if st.button("Apply kubectl scale deployment"):
        res = engine.k8s_autoscaler.scale_deployment(target_pods, reason="manual_user_override")
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
    st.markdown("Zero-latency offline classification engine masking sensitive payload data before emitting telemetry.")

    dlp_stats = engine.dlp_guardrail.get_stats()
    
    dc1, dc2, dc3 = st.columns(3)
    dc1.metric("Total Inspections", f"{dlp_stats['total_inspections']} Payloads")
    dc2.metric("PII Violations Detected", f"{dlp_stats['total_violations']} Violations")
    dc3.metric("Payload Clean Rate", f"{dlp_stats['clean_rate_pct']}%")

    st.markdown("### Live PII Masking Playground")
    sample_input = st.text_area(
        "Enter text containing sensitive data:",
        value="Customer SSN 123-45-6789 and Credit Card 4111-2222-3333-4444 email admin@google.com key sk-1234567890123456789020",
        height=100
    )

    if st.button("Inspect & Mask PII Payload"):
        res = engine.dlp_guardrail.inspect_and_mask(sample_input)
        
        if res.is_clean:
            st.success("✅ Payload is clean! No PII detected.")
        else:
            st.error(f"⚠️ PII Detected! Sensitivity Level: `{res.sensitivity}`")
            st.markdown(f"**Matched Rules**: `{res.matched_rules}`")
            st.markdown(f"**SHA-256 Signature**: `{res.data_hash}`")
            st.code(res.masked_text, language="text")

# -----------------------------------------------------------------------------
# TAB 5: Telemetry & Policy Logs
# -----------------------------------------------------------------------------
elif nav_choice == "📜 Telemetry & Policy Logs":
    st.subheader("📜 Prometheus / Grafana Metric Telemetry Exposition")
    st.markdown("Prometheus-compatible text exposition output for Grafana enterprise dashboards.")

    from extended_enterprise_dashboard import GrafanaMetricsExporter
    exporter = GrafanaMetricsExporter()
    
    prom_text = exporter.format_prometheus_metrics(
        engine.get_status(),
        engine.k8s_autoscaler.get_stats(),
        engine.dlp_guardrail.get_stats()
    )

    st.code(prom_text, language="text")
