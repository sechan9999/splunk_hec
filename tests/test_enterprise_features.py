"""Test suite for K8s HPA Autoscaler, Local DLP Guardrail, PyDeck Spatial Mapper, and Grafana Metrics.
"""

import asyncio
import threading
import time
import pytest
from async_agent_engine import AsyncAgentEngine, TaskPriority
from auto_remediation import AnomalyType
from k8s_hpa_autoscaler import K8sHPAAutoscaler
from local_dlp_guardrail import LocalDLPGuardrail
from extended_enterprise_dashboard import PyDeckFleetMapper, GrafanaMetricsExporter


def test_k8s_hpa_autoscaler():
    """Test Kubernetes deployment replica scaling and latency triggers."""
    scaler = K8sHPAAutoscaler(min_replicas=2, max_replicas=10)
    assert scaler.current_replicas == 2

    # Scale out on latency spike
    res = scaler.trigger_latency_scaleout(6200.0)
    assert res["scaled"] is True
    assert res["new_replicas"] == 8

    stats = scaler.get_stats()
    assert stats["current_replicas"] == 8
    assert stats["total_scaling_events"] == 1


def test_local_dlp_guardrail_masking():
    """Test local offline PII masking and sensitivity classification."""
    dlp = LocalDLPGuardrail()
    
    # Test clean text
    clean_res = dlp.inspect_and_mask("System operational log payload")
    assert clean_res.is_clean is True
    assert clean_res.sensitivity == "PUBLIC"

    # Test PII text (SSN, Valid Credit Card with Luhn, Email, API Key)
    pii_text = "User SSN 123-45-6789 and Card 4532-0151-1283-0366 email dev@google.com key sk-proj-1234567890123456789020"
    masked_res = dlp.inspect_and_mask(pii_text)
    
    assert masked_res.is_clean is False
    assert "SSN" in masked_res.matched_rules
    assert "CREDIT_CARD" in masked_res.matched_rules
    assert "EMAIL" in masked_res.matched_rules
    assert "API_KEY" in masked_res.matched_rules
    assert "[PII_MASKED:SSN]" in masked_res.masked_text
    assert "[PII_MASKED:CREDIT_CARD]" in masked_res.masked_text
    assert masked_res.sensitivity == "RESTRICTED"
    assert len(masked_res.data_hash) == 16


def test_dlp_luhn_and_kr_rrn():
    """Test Luhn algorithm card validation and Korean RRN classification."""
    dlp = LocalDLPGuardrail()

    # 16-digit Trace ID (invalid Luhn) should NOT be masked as Credit Card
    trace_id_text = "Trace ID 1739284756123456 generated"
    res_trace = dlp.inspect_and_mask(trace_id_text)
    assert "CREDIT_CARD" not in res_trace.matched_rules

    # Valid Visa card (valid Luhn) should be masked
    valid_card_text = "Billing card 4532015112830366"
    res_card = dlp.inspect_and_mask(valid_card_text)
    assert "CREDIT_CARD" in res_card.matched_rules
    assert "[PII_MASKED:CREDIT_CARD]" in res_card.masked_text

    # Korean RRN (900101-1234567) should be masked under KR_RRN
    rrn_text = "Customer ID 900101-1234567"
    res_rrn = dlp.inspect_and_mask(rrn_text)
    assert "KR_RRN" in res_rrn.matched_rules
    assert "[PII_MASKED:KR_RRN]" in res_rrn.masked_text


def test_pydeck_spatial_mapper():
    """Test PyDeck 3D spatial map JSON configuration generation."""
    mapper = PyDeckFleetMapper()
    config = mapper.generate_spatial_deck_config({"active_workers": 4, "throughput_tasks_per_sec": 38.5})
    
    assert "initialViewState" in config
    assert len(config["layers"]) == 2
    assert config["layers"][0]["id"] == "telemetry-nodes"
    assert config["layers"][1]["id"] == "telemetry-arcs"


def test_grafana_metrics_exporter():
    """Test Prometheus / Grafana text format metric exposition."""
    exporter = GrafanaMetricsExporter()
    prom_text = exporter.format_prometheus_metrics(
        engine_stats={"total_tasks": 15, "throughput_tasks_per_sec": 38.7, "total_remediations": 4},
        k8s_stats={"current_replicas": 8},
        dlp_stats={"total_violations": 2}
    )
    
    assert "unified_ops_tasks_total 15" in prom_text
    assert "unified_ops_k8s_replicas 8" in prom_text
    assert "unified_ops_dlp_violations_total 2" in prom_text


def test_streamlit_persistent_engine_lifecycle():
    """Test process-wide background event loop thread engine lifecycle."""
    eng = AsyncAgentEngine(num_workers=4)
    loop = asyncio.new_event_loop()
    t = threading.Thread(target=loop.run_forever, daemon=True)
    t.start()
    
    asyncio.run_coroutine_threadsafe(eng.start(), loop).result(timeout=5)
    eng._loop = loop

    def dummy_work():
        time.sleep(0.01)
        return "done"

    future = asyncio.run_coroutine_threadsafe(eng.submit_task(dummy_work, name="test_job", priority=TaskPriority.HIGH), loop)
    task = future.result(timeout=5)

    time.sleep(0.1)

    status = eng.get_status()
    assert status["is_running"] is True
    assert status["active_workers"] > 0
    assert status["total_processed"] > 0

    asyncio.run_coroutine_threadsafe(eng.stop(), loop).result(timeout=5)
    loop.call_soon_threadsafe(loop.stop)
    t.join(timeout=2)


@pytest.mark.asyncio
async def test_engine_k8s_and_dlp_integration():
    """Test AsyncAgentEngine automatically triggering K8s autoscaling and local DLP stats."""
    engine = AsyncAgentEngine(num_workers=2)
    await engine.start()

    # Trigger Latency Spike
    res = await engine.trigger_anomaly_remediation(AnomalyType.LATENCY_SPIKE, 6500.0)
    assert "k8s_autoscaling" in res
    assert res["k8s_autoscaling"]["new_replicas"] == 8

    # Process DLP text
    dlp_res = engine.dlp_guardrail.inspect_and_mask("Confidential API Key sk-proj-1234567890123456789020")
    assert dlp_res.is_clean is False

    status = engine.get_status()
    assert status["k8s_autoscaling"]["current_replicas"] == 8
    assert status["local_dlp"]["total_violations"] == 1

    await engine.stop()
