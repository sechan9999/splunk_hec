# All Things Agentic Hackathon — Submission Checklist

## 📋 Devpost Submission Form Answers

### 1. Project Basics & Eligibility
- **Built during submission period?**: Yes (Newly created during submission period)
- **Project Start Date (MM-DD-YY)**: **`08-24-26`** (August 24, 2026)
- **Google Model Used**: **Gemini 3.5 Flash**
- **Google Agent Framework Used**: **Google Agent Development Kit (ADK)** & **Google GenAI SDK**
- **Google Cloud Services Used**:
  - **Vertex AI / AI Platform** (Model Execution)
  - **Google Cloud Pub/Sub & Eventarc** (Real-Time Telemetry Stream Ingestion)
  - **Google Cloud Run** (Hosted Web Service)

### 2. Category Selection
- **Selected Category**: **Fortified Enterprise Fleet**
  *(Autonomous fleet management, asynchronous background agents, heavy-lifting telemetry ingest, multi-agent remediation, and security DLP guardrails).*

---

## 🔗 Links & Repositories

- **GitHub Repository Link**: [https://github.com/sechan9999/unified-ops-ax](https://github.com/sechan9999/unified-ops-ax) (mapped to `sechan9999/splunk_hec`)
- **Architecture Diagram**: Provided in [`architecture_diagram.md`](file:///c:/Users/secha/.gemini/antigravity-ide/scratch/unified-ops-ax/architecture_diagram.md).
- **Spin-Up Instructions**: Added to [`README.md`](file:///c:/Users/secha/.gemini/antigravity-ide/scratch/unified-ops-ax/README.md) and [`HACKATHON_SUBMISSION.md`](file:///c:/Users/secha/.gemini/antigravity-ide/scratch/unified-ops-ax/HACKATHON_SUBMISSION.md).
- **Reproducible Testing Instructions**: Section added to [`README.md`](file:///c:/Users/secha/.gemini/antigravity-ide/scratch/unified-ops-ax/README.md) (`pytest tests/ -v`, `python hackathon_showcase.py`, `python verify.py`). (mapped to `sechan9999/splunk_hec`)
- **Private Access Granted To**:
  - `testing@devpost.com`
  - `cloudhackathons@google.com`
- **Hosted Project URL**: [https://unified-ops.streamlit.app/](https://unified-ops.streamlit.app/)
- **Testing Credentials**: Not required (Public Streamlit Web App).

---

## 🎥 Demo Video Outline (< 4 Minutes)

### Target Duration: 2 minutes 30 seconds

| Time | Scene | Focus / Narration |
| :--- | :--- | :--- |
| **0:00 - 0:15** | **The Hook** | Show 1,000 log events stream ingesting asynchronously and triggering instant sub-10ms auto-remediation in ADK Web UI. |
| **0:15 - 0:45** | **Background Agent Engine (`AsyncAgentEngine`)** | Show priority worker queue (`CRITICAL` -> `LOW`) processing 38+ tasks/sec without blocking UI. |
| **0:45 - 1:15** | **Multi-Region GCP Streaming** | Show real-time stream ingestion from GCP Cloud Pub/Sub (`us-central1`), Eventarc (`asia-east1`), and Kafka (`europe-west1`). |
| **1:15 - 1:45** | **Splunk Telemetry & Remediation** | Show live policy switching (Cost Spike -> cheap model fallback, DLP violation burst -> strict blocking). |
| **1:45 - 2:15** | **GCP Backend Proof** | Show GCP Cloud Console Pub/Sub topics, Cloud Run logs, and Vertex AI API call metrics. |
| **2:15 - 2:30** | **Conclusion** | Summary of self-healing AI fleet architecture. |

---

## 📝 Disclosures & Pre-existing Code

- **Pre-existing / Third-Party Libraries Used**:
  - **Google Agent Development Kit (ADK)** (Open Source Framework)
  - **Context7 Upstash Client** (Documentation Retrieval)
  - **Splunk HEC Emitter** (Telemetry Transport)
  - **Pytest / Pydantic / FastAPI / Uvicorn** (Standard Python Ecosystem)
- **Original Work Developed during Hackathon**:
  - `AsyncAgentEngine` background worker queue & priority state machine
  - `pubsub_kafka_stream_processor.py` multi-region GCP Pub/Sub & Kafka stream coordinator
  - `auto_remediation.py` dynamic router weight tuner & circuit breaker loop
  - `hackathon_showcase.py` & automated test suite (20 unit/integration tests)

---

## 📣 Bonus Points & Social Media Share

- **Hashtags**: `#AllThingsAgenticHackathon` `#GoogleCloud` `#Gemini`
- **Social Handles**: Shared on X and LinkedIn.
