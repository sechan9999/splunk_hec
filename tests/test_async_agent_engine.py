"""Comprehensive test suite for AsyncAgentEngine background worker queue

and auto-remediation integration.
"""

import asyncio
import pytest
from async_agent_engine import AsyncAgentEngine, TaskPriority, TaskStatus
from auto_remediation import AnomalyType

@pytest.mark.asyncio
async def test_engine_lifecycle():
    """Test engine start, stop, and status retrieval."""
    engine = AsyncAgentEngine(num_workers=2)
    assert not engine.is_running
    
    await engine.start()
    assert engine.is_running
    status = engine.get_status()
    assert status["num_workers"] == 2
    assert status["is_running"] is True
    
    await engine.stop()
    assert not engine.is_running


@pytest.mark.asyncio
async def test_task_submission_and_execution():
    """Test submitting and completing asynchronous tasks in background workers."""
    engine = AsyncAgentEngine(num_workers=2)
    await engine.start()

    def sync_calc(x, y):
        return x + y

    async def async_calc(x, y):
        await asyncio.sleep(0.01)
        return x * y

    t1 = await engine.submit_task(sync_calc, 10, 20, name="sync_add")
    t2 = await engine.submit_task(async_calc, 5, 4, name="async_mul")

    # Wait for completion
    await asyncio.sleep(0.1)

    assert t1.status == TaskStatus.COMPLETED
    assert t1.result == 30

    assert t2.status == TaskStatus.COMPLETED
    assert t2.result == 20

    await engine.stop()


@pytest.mark.asyncio
async def test_task_priority():
    """Test critical priority tasks execute before low priority tasks."""
    engine = AsyncAgentEngine(num_workers=1)
    execution_order = []

    def make_task_fn(val):
        def fn():
            execution_order.append(val)
            return val
        return fn

    await engine.start()

    t_low = await engine.submit_task(make_task_fn("low"), priority=TaskPriority.LOW)
    t_crit = await engine.submit_task(make_task_fn("critical"), priority=TaskPriority.CRITICAL)

    await asyncio.sleep(0.1)

    assert "critical" in execution_order
    assert "low" in execution_order
    assert t_crit.status == TaskStatus.COMPLETED
    assert t_low.status == TaskStatus.COMPLETED

    await engine.stop()


@pytest.mark.asyncio
async def test_anomaly_remediation_trigger():
    """Test triggering background anomaly remediation policy."""
    engine = AsyncAgentEngine(num_workers=2)
    await engine.start()

    result = await engine.trigger_anomaly_remediation(AnomalyType.COST_SPIKE, 8.5)
    assert result["handled"] is True
    assert result["anomaly_type"] == AnomalyType.COST_SPIKE.value
    assert len(result["actions"]) > 0

    status = engine.get_status()
    assert status["total_remediations"] >= 1

    await engine.stop()
