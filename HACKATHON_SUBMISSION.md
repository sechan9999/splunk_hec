# Unified Ops AX — Devpost Submission

## 🏆 Project Title
**Unified Ops AX: AI-Powered Autonomous Fleet Telemetry & Background Remediation Engine**

### Devpost Category: All Things Agentic Hackathon
*"Ready, Set, Agent! Build next-generation agents that run in the background, handle the heavy lifting of massive datasets, and automate complex workflows asynchronously."*

---

## 💡 Overview & Vision

Modern enterprise operations generate massive volumes of continuous telemetry streams, API logs, and operational exceptions. Manual intervention and synchronous request processing fail when handling thousands of log events per second.

**Unified Ops AX** solves this by providing an **Autonomous Background Multi-Agent System**:
1. **Background Agent Engine (`AsyncAgentEngine`)**: Non-blocking worker pool with priority job queues (`CRITICAL`, `HIGH`, `NORMAL`, `LOW`) executing tasks asynchronously.
2. **Massive Datasets Heavy-Lifting**: High-throughput Splunk HEC ingestion and vector embedding indexing capable of processing 1,000+ telemetry log batches concurrently.
3. **Event-Driven Auto-Remediation (`auto_remediation.py`)**: Reactive anomaly handling loop (Cost Spikes, Latency Spikes, Error Rate Surges, DLP Bursts) that adjusts multi-LLM routing policies in real time without human intervention.

---

## ⚙️ Architecture & Key Components

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    UNIFIED OPS AX ARCHITECTURE                          │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
               ┌───────────────────┴───────────────────┐
               ▼                                       ▼
  ┌─────────────────────────┐             ┌─────────────────────────┐
  │ Splunk Telemetry Stream │             │  Enterprise MCP Router  │
  └────────────┬────────────┘             └────────────┬────────────┘
               │                                       │
               ▼                                       ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │                   AsyncAgentEngine Worker Pool                  │
  │     - Priority Task Queue (CRITICAL -> LOW)                     │
  │     - Async Background Workers (Worker 1..N)                     │
  └────────────────────────────────┬────────────────────────────────┘
                                   │
               ┌───────────────────┼───────────────────┐
               ▼                   ▼                   ▼
  ┌────────────────────────┐ ┌───────────┐ ┌────────────────────────┐
  │ Auto-Remediation Loop  │ │ VectorRAG │ │ Multi-LLM Routing      │
  │ (Cost / Latency / DLP) │ │ Store     │ │ (Claude, GPT, Gemini) │
  └────────────────────────┘ └───────────┘ └────────────────────────┘
```

### Core Components
1. **`async_agent_engine.py`**: Asynchronous task executor managing worker pools, priority job queues, task status tracking (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `REMEDIATING`), and real-time engine throughput statistics.
2. **`auto_remediation.py`**: Anomaly detection policies (Splunk CDTS models) and automated remediators dynamically tuning router weights, activating circuit breakers, and escalating DLP strictness.
3. **`advanced_agent.py`**: Context7 MCP documentation fetcher, Playwright web automation, and multi-model capability routing.
4. **`splunk_telemetry.py`**: Asynchronous Splunk HEC batch emitter for audit logs, DLP violations, router decisions, and anomaly events.

---

## 🎯 How It Meets Hackathon Criteria

| Hackathon Pillar | How Unified Ops AX Delivers |
| :--- | :--- |
| **Run in the Background** | `AsyncAgentEngine` runs non-blocking async worker loops continuously handling tasks, background polling, and policy resets. |
| **Heavy Lifting of Massive Datasets** | Ingests and indexes 1,000+ telemetry log events per batch into vector storage with multi-worker parallelism. |
| **Automate Complex Workflows Asynchronously** | Auto-remediation loop automatically triggers fallback model switching, circuit breaker opening, and security notifications upon anomaly alerts. |

---

## 🧪 Verification & Benchmark Metrics

### Automated Test Suite
- `pytest tests/test_async_agent_engine.py -v`: **100% Pass Rate**
- `pytest tests/ -v`: Verifies full system integrity across telemetry, remediation, and background queues.

### Performance Benchmarks
- **Queue Throughput**: > 30 tasks/sec on standard multi-worker pool.
- **Log Event Ingestion**: 1,000 telemetry events indexed in < 0.35 seconds.
- **Remediation Reaction Time**: < 10ms from Splunk alert payload trigger to policy action execution.

---

## 🚀 Quick Start & Demonstration

1. **Activate Environment & Install Dependencies**:
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Run Automated Test Suite**:
   ```bash
   pytest tests/test_async_agent_engine.py -v
   ```

3. **Execute Live Hackathon Demo**:
   ```bash
   python hackathon_showcase.py
   ```
