"""Real-Time Streaming Module for GCP Cloud Pub/Sub, Eventarc, and Apache Kafka.

Scales AsyncAgentEngine to consume multi-region streaming topics for global
telemetry ingestion and real-time auto-remediation.
"""

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from auto_remediation import AnomalyType

logger = logging.getLogger("stream_processor")


@dataclass
class StreamMessage:
    """Represents a message from GCP Pub/Sub or Kafka."""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_type: str = "pubsub"  # "pubsub", "eventarc", "kafka"
    region: str = "us-central1"
    topic: str = "telemetry-stream"
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class GCPPubSubSubscriber:
    """Subscriber for GCP Cloud Pub/Sub and Eventarc triggers."""

    def __init__(self, project_id: str = "project-d62ae2f7-d26e-4c58-b22", topic_name: str = "telemetry-stream"):
        self.project_id = project_id
        self.topic_name = topic_name
        self.subscription_path = f"projects/{project_id}/subscriptions/{topic_name}-sub"
        self.is_listening = False
        self._consumed_count = 0

    async def publish_simulated_event(self, event_data: Dict[str, Any], region: str = "us-central1") -> StreamMessage:
        """Simulates publishing/receiving a GCP Pub/Sub or Eventarc event."""
        self._consumed_count += 1
        msg = StreamMessage(
            source_type="pubsub",
            region=region,
            topic=self.topic_name,
            payload=event_data
        )
        logger.info(f"[GCP Pub/Sub:{region}] Published message {msg.message_id} to {self.subscription_path}")
        return msg

    def get_stats(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "subscription": self.subscription_path,
            "consumed_count": self._consumed_count
        }


class KafkaStreamConsumer:
    """Consumer for Apache Kafka topics."""

    def __init__(self, bootstrap_servers: str = "localhost:9092", topic_name: str = "telemetry-events-topic"):
        self.bootstrap_servers = bootstrap_servers
        self.topic_name = topic_name
        self.is_listening = False
        self._consumed_count = 0

    async def consume_simulated_message(self, event_data: Dict[str, Any], region: str = "europe-west1") -> StreamMessage:
        """Simulates consuming a message from a Kafka topic partition."""
        self._consumed_count += 1
        msg = StreamMessage(
            source_type="kafka",
            region=region,
            topic=self.topic_name,
            payload=event_data
        )
        logger.info(f"[Kafka:{region}] Consumed message {msg.message_id} from {self.topic_name}")
        return msg

    def get_stats(self) -> Dict[str, Any]:
        return {
            "bootstrap_servers": self.bootstrap_servers,
            "topic": self.topic_name,
            "consumed_count": self._consumed_count
        }


class StreamIngestManager:
    """Multi-Region Streaming Manager routing Pub/Sub, Eventarc, and Kafka to AsyncAgentEngine."""

    def __init__(self, agent_engine=None):
        self.agent_engine = agent_engine
        self.pubsub_subscriber = GCPPubSubSubscriber()
        self.kafka_consumer = KafkaStreamConsumer()
        self.is_active = False
        self.regions = ["us-central1", "europe-west1", "asia-east1"]
        self.total_stream_messages = 0

    def set_engine(self, engine):
        self.agent_engine = engine

    async def process_stream_message(self, message: StreamMessage) -> Dict[str, Any]:
        """Parses stream message and dispatches task/remediation to AsyncAgentEngine."""
        self.total_stream_messages += 1
        payload = message.payload

        # Check if message is an anomaly alert payload
        if "anomaly_type" in payload:
            anomaly_str = payload.get("anomaly_type")
            metric_val = float(payload.get("metric_value", 0.0))
            
            try:
                anomaly_type = AnomalyType(anomaly_str)
            except ValueError:
                anomaly_type = anomaly_str

            if self.agent_engine:
                result = await self.agent_engine.trigger_anomaly_remediation(anomaly_type, metric_val)
                return {
                    "status": "remediation_triggered",
                    "source": message.source_type,
                    "region": message.region,
                    "result": result
                }

        # Routine telemetry log event -> enqueue task
        if self.agent_engine:
            async def log_indexer_task():
                await asyncio.sleep(0.01)
                return f"Indexed stream event {message.message_id} from {message.region}"

            task = await self.agent_engine.submit_task(
                log_indexer_task,
                name=f"stream_ingest_{message.source_type}_{message.region}"
            )
            return {
                "status": "enqueued",
                "source": message.source_type,
                "region": message.region,
                "task_id": task.task_id
            }

        return {"status": "received_no_engine", "source": message.source_type}

    def get_stats(self) -> Dict[str, Any]:
        return {
            "is_active": self.is_active,
            "regions_monitored": self.regions,
            "total_stream_messages": self.total_stream_messages,
            "pubsub": self.pubsub_subscriber.get_stats(),
            "kafka": self.kafka_consumer.get_stats()
        }
