# Unified Ops AX — Demo Video Script (< 3 Minutes)

**App URL**: [https://unified-ops.streamlit.app/](https://unified-ops.streamlit.app/)  
**Target Duration**: 2 Minutes 30 Seconds  
**Category**: Fortified Enterprise Fleet  
**Technologies**: Google Cloud + Gemini 3.5 Flash + Google ADK  

---

## 🎬 Second-by-Second Video Script & Voiceover Guide

### ⏱️ 0:00 - 0:15 | The 10-Second Hook (Immediate Action)
- **Visual**: Screen starts directly on **`https://unified-ops.streamlit.app/`** showing the **🌐 Global 3D Fleet Map**. 
- **Voiceover**: 
  > *"Managing enterprise AI fleets at scale means handling millions of telemetry logs, cost spikes, and security risks. Meet **Unified Ops AX**, an autonomous background multi-agent engine built with Google ADK, Gemini 3.5 Flash, and Google Cloud."*

---

### ⏱️ 0:15 - 0:45 | Real-Time Multi-Region Streaming & PyDeck 3D Map
- **Visual**: Hover over the 3D PyDeck spatial flow arcs connecting `us-central1` (Iowa), `europe-west1` (Belgium), and `asia-east1` (Taiwan).
- **Voiceover**: 
  > *"Here on our PyDeck 3D control map, Unified Ops AX ingests live multi-region telemetry streams from Google Cloud Pub/Sub, GCP Eventarc, and Apache Kafka in real time—processing over 2,000 log events in under 0.3 seconds without blocking user applications."*

---

### ⏱️ 0:45 - 1:15 | Asynchronous Engine & Priority Worker Queue
- **Visual**: Click on **`⚡ Async Engine & Workers`** tab. Click **"Enqueue Batch Ingest Job"** and **"Trigger Auto-Remediation Policy"**.
- **Voiceover**: 
  > *"Our core engine, `AsyncAgentEngine`, runs non-blocking background workers with priority queues (`CRITICAL` to `LOW`). When a Splunk alert detects an hourly cost spike over \$5.00, our agent instantly reroutes queries to lower-cost Gemini models and enables aggressive caching in sub-10 milliseconds."*

---

### 1:15 - 1:45 | Kubernetes HPA Pod Autoscaling & Local DLP Guardrail
- **Visual**: Switch to **`☸️ K8s HPA Pod Scaling`** tab showing pod replicas scaling from 2 to 8 pods. Then switch to **`🔒 Local DLP Guardrail`** tab and click **"Inspect & Mask PII Payload"**.
- **Voiceover**: 
  > *"When latency bursts hit 6,000 milliseconds, our Kubernetes HPA autoscaler automatically scales deployment worker pods from 2 to 8 replicas. On the security front, our zero-latency local DLP guardrail redacts sensitive SSNs, credit cards, and API keys before telemetry is emitted—generating SHA-256 cryptographic signatures."*

---

### 1:45 - 2:15 | Prometheus / Grafana Metric Endpoint & Proof of GCP Backend
- **Visual**: Switch to **`📜 Telemetry & Policy Logs`** tab showing Prometheus `/metrics` exposition text. Show GCP Cloud Console / Cloud Run logs brief clip.
- **Voiceover**: 
  > *"For enterprise ops desks, Unified Ops AX exports native Prometheus metrics for Grafana dashboards. The entire backend runs serverless on Google Cloud, utilizing Vertex AI for Gemini 3.5 Flash inference and Cloud Pub/Sub for event streaming."*

---

### 2:15 - 2:30 | Conclusion & Call to Action
- **Visual**: Zoom out to full Streamlit Control Center header with URL `https://unified-ops.streamlit.app/`.
- **Voiceover**: 
  > *"Unified Ops AX brings self-healing, autonomous intelligence to enterprise AI fleets. Check out our live app at `unified-ops.streamlit.app`. Thank you!"*

---

## 💡 Video Recording Pro Tips Checklist
- [x] **No login/setup footage**: Video starts already loaded on `https://unified-ops.streamlit.app/`.
- [x] **No live typing**: Paste sample text or click pre-built buttons.
- [x] **Pacing**: Use jump cuts to keep momentum fast and eliminate dead air.
- [x] **On-screen text**: Add sub-titles for key metrics (`> 38 tasks/sec`, `Sub-10ms Auto-Remediation`, `2 -> 8 K8s Pod Replicas`).
