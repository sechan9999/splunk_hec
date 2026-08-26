"""Test suite for GCP Pub/Sub, Eventarc, and Apache Kafka real-time streaming processor.
"""

import asyncio
import pytest
from async_agent_engine import AsyncAgentEngine
from auto_remediation import AnomalyType
from pubsub_kafka_stream_processor import (
    GCPPubSubSubscriber,
    KafkaStreamConsumer,
    StreamIngestManager,
    StreamMessage
)

@pytest.mark.asyncio
async def test_gcp_pubsub_subscriber():
    """Test GCP Pub/Sub subscriber event simulation and stats."""
    pubsub = GCPPubSubSubscriber(project_id="project-d62ae2f7-d26e-4c58-b22", topic_name="telemetry-stream")
    msg = await pubsub.publish_simulated_event({"event": "log_batch", "count": 100}, region="us-central1")
    
    assert msg.source_type == "pubsub"
    assert msg.region == "us-central1"
    assert pubsub.get_stats()["consumed_count"] == 1


@pytest.mark.asyncio
async def test_kafka_stream_consumer():
    """Test Kafka consumer message simulation and stats."""
    kafka = KafkaStreamConsumer(bootstrap_servers="localhost:9092", topic_name="telemetry-events-topic")
    msg = await kafka.consume_simulated_message({"event": "metric_ingest"}, region="europe-west1")
    
    assert msg.source_type == "kafka"
    assert msg.region == "europe-west1"
    assert kafka.get_stats()["consumed_count"] == 1


@pytest.mark.asyncio
async def test_stream_ingest_manager_with_engine():
    """Test StreamIngestManager integrating with AsyncAgentEngine for real-time task and remediation handling."""
    engine = AsyncAgentEngine(num_workers=2)
    await engine.start()

    manager = engine.stream_manager

    # Test routine stream message
    msg_routine = StreamMessage(
        source_type="pubsub",
        region="us-central1",
        topic="telemetry-stream",
        payload={"log_count": 500}
    )
    res_routine = await manager.process_stream_message(msg_routine)
    assert res_routine["status"] == "enqueued"

    # Test anomaly alert stream message (Cost Spike)
    msg_alert = StreamMessage(
        source_type="kafka",
        region="asia-east1",
        topic="anomaly-alerts-topic",
        payload={"anomaly_type": "cost_spike", "metric_value": 9.2}
    )
    res_alert = await manager.process_stream_message(msg_alert)
    assert res_alert["status"] == "remediation_triggered"
    assert res_alert["result"]["handled"] is True

    await asyncio.sleep(0.1)

    status = engine.get_status()
    assert status["streaming_ingest"]["total_stream_messages"] == 2
    assert status["total_remediations"] >= 1

    await engine.stop()
