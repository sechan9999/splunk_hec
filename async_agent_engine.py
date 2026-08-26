"""Asynchronous Agent Engine & Background Task Queue for Unified Ops AX.

Built for All Things Agentic Hackathon on Devpost:
- Asynchronous worker pool for background execution.
- High-volume telemetry stream ingestion and anomaly handling.
- Event-driven background auto-remediation and policy switching.
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from auto_remediation import AnomalyType, AnomalyHandler, DEFAULT_POLICIES
from splunk_telemetry import SplunkTelemetry, get_telemetry
from pubsub_kafka_stream_processor import StreamIngestManager, StreamMessage
from k8s_hpa_autoscaler import K8sHPAAutoscaler
from local_dlp_guardrail import LocalDLPGuardrail

logger = logging.getLogger("async_agent_engine")


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REMEDIATING = "REMEDIATING"


class TaskPriority(int, Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class AgentTask:
    """Represents a background agent task."""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "default_task"
    func: Optional[Callable[..., Any]] = None
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Any = None
    error: Optional[str] = None
    remediation_applied: Optional[Dict[str, Any]] = None


class AsyncAgentEngine:
    """Asynchronous Multi-Agent Engine managing background workers and stream processing."""

    def __init__(self, num_workers: int = 4):
        self.num_workers = num_workers
        self.task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.tasks: Dict[str, AgentTask] = {}
        self.workers: List[asyncio.Task] = []
        self.is_running: bool = False
        self.telemetry = get_telemetry()
        self.anomaly_handler = AnomalyHandler()
        self.stream_manager = StreamIngestManager(agent_engine=self)
        self.k8s_autoscaler = K8sHPAAutoscaler()
        self.dlp_guardrail = LocalDLPGuardrail()
        
        # Performance metrics
        self.total_processed: int = 0
        self.total_remediations: int = 0
        self.start_time: Optional[float] = None

    async def start(self):
        """Starts background worker tasks."""
        if self.is_running:
            return
        self.is_running = True
        self.start_time = time.time()
        for worker_id in range(self.num_workers):
            task = asyncio.create_task(self._worker_loop(worker_id))
            self.workers.append(task)
        logger.info(f"AsyncAgentEngine started with {self.num_workers} background workers.")

    async def stop(self):
        """Gracefully stops background worker pool."""
        if not self.is_running:
            return
        self.is_running = False
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        logger.info("AsyncAgentEngine stopped.")

    async def submit_task(
        self,
        func: Callable[..., Any],
        *args,
        name: str = "task",
        priority: TaskPriority = TaskPriority.NORMAL,
        **kwargs
    ) -> AgentTask:
        """Submits an asynchronous agent task to the background queue."""
        task = AgentTask(
            name=name,
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            status=TaskStatus.PENDING
        )
        self.tasks[task.task_id] = task
        # PriorityQueue sorts by lower value first, so invert priority
        sort_key = (5 - int(priority), task.created_at, task.task_id)
        await self.task_queue.put((sort_key, task))
        logger.info(f"Task submitted: {task.name} ({task.task_id}) [Priority: {priority.name}]")
        return task

    async def trigger_anomaly_remediation(self, anomaly_type: AnomalyType, metric_value: float) -> Dict[str, Any]:
        """Asynchronously triggers background anomaly detection and auto-remediation policy execution."""
        task_id = str(uuid.uuid4())
        remediation_task = AgentTask(
            task_id=task_id,
            name=f"anomaly_remediation_{anomaly_type.value}",
            priority=TaskPriority.CRITICAL,
            status=TaskStatus.REMEDIATING
        )
        self.tasks[task_id] = remediation_task

        # Execute policy remediation asynchronously
        payload = {
            "result": {
                "anomaly_type": anomaly_type.value if isinstance(anomaly_type, AnomalyType) else anomaly_type,
                "metric_value": metric_value
            }
        }
        res = self.anomaly_handler.handle(payload)

        # Trigger K8s HPA Pod Scaling if Latency Spike detected
        anomaly_enum = AnomalyType.LATENCY_SPIKE if anomaly_type in ("latency_spike", AnomalyType.LATENCY_SPIKE) else None
        if anomaly_enum:
            k8s_res = self.k8s_autoscaler.trigger_latency_scaleout(metric_value)
            res["k8s_autoscaling"] = k8s_res

        remediation_task.status = TaskStatus.COMPLETED
        remediation_task.completed_at = time.time()
        remediation_task.result = res
        remediation_task.remediation_applied = res

        self.total_remediations += 1
        self.telemetry.emit_anomaly(
            anomaly_type=anomaly_type.value if isinstance(anomaly_type, AnomalyType) else str(anomaly_type),
            metric_name="background_remediation",
            current_value=metric_value,
            threshold=5.0,
            remediation_triggered=True
        )
        logger.info(f"Background Remediation Completed: {anomaly_type} -> Result: {res}")
        return res

    async def _worker_loop(self, worker_id: int):
        """Worker loop processing background tasks asynchronously."""
        while self.is_running:
            try:
                # Wait for next task from priority queue
                sort_key, task = await asyncio.wait_for(self.task_queue.get(), timeout=0.5)
                task.status = TaskStatus.RUNNING
                task.started_at = time.time()

                try:
                    if asyncio.iscoroutinefunction(task.func):
                        res = await task.func(*task.args, **task.kwargs)
                    else:
                        res = await asyncio.to_thread(task.func, *task.args, **task.kwargs)
                    
                    task.result = res
                    task.status = TaskStatus.COMPLETED
                    self.total_processed += 1
                except Exception as e:
                    task.error = str(e)
                    task.status = TaskStatus.FAILED
                    logger.error(f"Worker-{worker_id} Task {task.name} failed: {e}")
                finally:
                    task.completed_at = time.time()
                    self.task_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker-{worker_id} unexpected error: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Returns engine status, background statistics, and active job counts."""
        pending_count = sum(1 for t in self.tasks.values() if t.status == TaskStatus.PENDING)
        running_count = sum(1 for t in self.tasks.values() if t.status == TaskStatus.RUNNING)
        completed_count = sum(1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETED)
        failed_count = sum(1 for t in self.tasks.values() if t.status == TaskStatus.FAILED)

        uptime_sec = round(time.time() - self.start_time, 2) if self.start_time else 0.0
        throughput = round(self.total_processed / uptime_sec, 2) if uptime_sec > 0 else 0.0
        active_workers = sum(1 for w in self.workers if not w.done()) if self.workers else 0
        return {
            "is_running": self.is_running and active_workers > 0,
            "active_workers": active_workers,
            "num_workers": self.num_workers,
            "uptime_sec": uptime_sec,
            "throughput_tasks_per_sec": throughput,
            "total_tasks": len(self.tasks),
            "total_processed": self.total_processed,
            "total_remediations": self.total_remediations,
            "streaming_ingest": self.stream_manager.get_stats(),
            "k8s_autoscaling": self.k8s_autoscaler.get_stats(),
            "local_dlp": self.dlp_guardrail.get_stats(),
            "counts": {
                "pending": pending_count,
                "running": running_count,
                "completed": completed_count,
                "failed": failed_count
            }
        }
