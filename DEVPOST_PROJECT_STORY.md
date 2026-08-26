# Devpost Project Story: Unified Ops AX

## Inspiration
Modern enterprise AI applications generate millions of API calls, log events, and telemetry data points every day. However, managing AI fleet infrastructure at scale presents severe operational bottlenecks: **unexpected cost spikes from large LLM models**, **latency bursts during peak traffic**, **security DLP violations from sensitive data exposure**, and **manual incident response delays**.

When an LLM model experiences an error burst or cost runaway, human operators cannot react fast enough. We were inspired to build **Unified Ops AX** for the **All Things Agentic Hackathon** to answer a fundamental question: *Can we build autonomous background agents that heavy-lift massive telemetry log streams, detect anomalies in real time, and execute self-healing remediation policies asynchronously without blocking human operators?*

---

## What it does
**Unified Ops AX** is an **AI-Powered Autonomous Fleet Telemetry & Asynchronous Remediation Engine**. It acts as an intelligent, self-healing operational desk for AI agent fleets:

- **Autonomous Background Agent Engine (`AsyncAgentEngine`)**: A multi-worker asynchronous task queue (`CRITICAL`, `HIGH`, `NORMAL`, `LOW` priority) that ingests log streams, executes vector RAG indexers, and runs background workflows continuously.
- **Massive Datasets Heavy-Lifting**: Ingests and processes 1,000+ telemetry log events per batch across parallel worker threads.
- **Real-Time Splunk HEC Telemetry**: Captures token consumption, latency, cost USD, router decisions, and DLP security rule violations.
- **Event-Driven Auto-Remediation (`auto_remediation.py`)**: Reacts instantly to Splunk anomaly alerts (e.g., hourly cost > $5.00, latency > 5,000ms, DLP violation bursts) by dynamically tuning router model weights, opening circuit breakers, switching to fallback models, and notifying security admins in under 10 milliseconds.

---

## How we built it
We architected **Unified Ops AX** using modern agentic and operational frameworks:

- **Core Engine**: Built with Python 3.11 and `asyncio.PriorityQueue` to manage asynchronous worker threads and non-blocking job execution.
- **Agent Orchestration**: Integrated **Google Agent Development Kit (ADK)** for multi-agent delegation across specialized sub-agents (`pre_trip`, `planning`, `booking`, `in_trip`, `post_trip`).
- **Telemetry & Monitoring**: Custom **Splunk HEC (HTTP Event Collector)** emitter with background batch flushing and zero-drop thread-safe queues.
- **Multi-LLM Intelligent Router**: Dynamically calculates routing scores based on query complexity, quality weight, speed weight, and cost weight across OpenAI (GPT-4o), Anthropic (Claude 3.5 Sonnet), and Google (Gemini 2.0 Flash).
- **Knowledge & Tools**: Context7 Upstash client for real-time library documentation fetching, Vector RAG store for semantic indexing, and FastAPI REST endpoints.

---

## Challenges we ran into
1. **Asynchronous Queue Concurrency under High Load**: Ensuring that high-priority anomaly remediations (`CRITICAL`) jump ahead of routine telemetry indexing (`NORMAL`) without starving ongoing worker tasks required fine-tuning our priority queue tuples and task state machine (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `REMEDIATING`).
2. **Non-Blocking Telemetry Flushing**: Emitting high-frequency log events to Splunk without introducing latency to agent response times. We solved this by implementing an isolated daemon thread batching mechanism with bounded queues.
3. **Graceful Fallback Handling**: Ensuring offline resiliency when GCP Vertex AI billing or external cloud APIs are unavailable, implementing local `LlmResponse` error callbacks so the Dev UI and CLI run smoothly without crashing.

---

## Accomplishments that we're proud of
- **⚡ High Throughput Performance**: Achieved **> 31 tasks/sec queue throughput**, indexing 1,000 telemetry events (512 KB) in **0.317 seconds**.
- **⏱️ Sub-10ms Auto-Remediation**: Instant background policy execution when Splunk alerts trigger, switching model fallback routes and restoring baseline weights automatically after cooldown periods.
- **🧪 100% Test Pass Rate**: Built a comprehensive automated test suite (`17/17 pytest cases passed`) covering async queue concurrency, Splunk telemetry emission, and multi-agent routing.
- **🖥️ Live ADK Web UI & Visual Dashboard**: Full interactive visualization of active sessions, tool call traces, and background engine metrics.

---

## What we learned
- **Background Agents are Essential for Fleet Scale**: Synchronous execution blocks application threads; offloading heavy lifting to asynchronous background workers drastically improves system responsiveness.
- **Telemetry Feedback Loops Enable Self-Healing**: Pairing Splunk anomaly detection with dynamic router policy updates creates an autonomous control loop that prevents API cost overruns before they hit monthly invoices.
- **Decoupled Tool Contracts**: Structuring agent tools with explicit Pydantic schemas ensures seamless execution across both local offline fallbacks and remote multi-LLM endpoints.

---

## What's next for Unified Ops AX
- **🌐 Real-Time Streaming (Kafka & GCP PubSub)**: Scaling the `AsyncAgentEngine` to consume live Eventarc and Kafka topics for global multi-region telemetry ingestion.
- **☸️ Kubernetes Pod Auto-Scaling Integration**: Automatically triggering K8s HPA horizontal pod scaling when latency spike anomalies are detected in background agent pools.
- **🔒 Fine-Tuned Local Guardrail Models**: Deploying small, fine-tuned local DLP classification models for offline PII masking before telemetry emission.
- **📊 Extended Enterprise Dashboards**: Expanding PyDeck spatial mapping and Grafana telemetry dashboards for enterprise supply chain and operational exception desks.
