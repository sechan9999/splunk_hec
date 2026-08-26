# 🚀 Unified Ops AX — Gemini Ops Fleet

> **Devpost Submission for [All Things Agentic Hackathon](https://allthingsagentichackathon.devpost.com/) (Google Cloud & Vertex AI)**  
> **Repository:** [`sechan9999/unified-ops-ax`](https://github.com/sechan9999/unified-ops-ax)  
> **Core Principle:** *"The instruction is a courtesy; the code is the contract."*

[![Live Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://unified-ops.streamlit.app/)
[![GitHub Repo](https://img.shields.io/badge/GitHub-sechan9999%2Funified--ops--ax-blue?logo=github)](https://github.com/sechan9999/unified-ops-ax)
[![Build & Verify Status](https://img.shields.io/badge/Tests-25%20Passed-brightgreen.svg)]()
[![Google Cloud](https://img.shields.io/badge/Google%20Cloud-Vertex%20AI%20%7C%20ADK%20%7C%20Cloud%20Run-4285F4.svg)]()
[![Model](https://img.shields.io/badge/LLM-Gemini%203.5%20Flash-34A853.svg)]()

---

## 🌐 Live Web App & Screenshots

👉 **Live Control Center**: **[https://unified-ops.streamlit.app/](https://unified-ops.streamlit.app/)** *(Alternative: [https://splunkax.streamlit.app/](https://splunkax.streamlit.app/))*  
👉 **GitHub Repository**: **[https://github.com/sechan9999/unified-ops-ax](https://github.com/sechan9999/unified-ops-ax)**

### 🖥️ App Control Center Screenshots

![Unified Ops AX Streamlit Control Center](../assets/streamlit_dashboard.png)
*Unified Ops AX Control Center displaying real-time 3D spatial flow map, background worker metrics, and K8s pod scaling controls.*

![PyDeck 3D Spatial Fleet Map](../assets/pydeck_3d_map.png)
*PyDeck 3D Spatial Fleet Flow Map displaying multi-region telemetry ingest across GCP `us-central1` (Iowa), `europe-west1` (Belgium), and `asia-east1` (Taiwan).*

---

## 🎯 Inspiration

A fifty-person manufacturing company we know has no IT department. Sales, support, accounting, and the owner each keep their own spreadsheets, and a support ticket that arrives at two in the morning sits until someone opens a laptop. They are exactly the kind of company agents should help.

They are also the kind of company that cannot survive an agent emailing a customer something wrong, or handing a sales rep the margin memo before the quarter closes. Every agent demo we looked at answered *"how much can it do on its own?"* Nobody was answering *"what is it structurally unable to do?"* — which is the only question a company without a compliance team can actually act on.

So we inverted the pitch. **This project is not interesting because the agents are autonomous. It is interesting because of what they are prevented from reaching, and because those limits are enforced in code rather than requested in a prompt.**

---

## 🛡️ What It Does

**Gemini Ops Fleet** is a fleet of four governed back-office agents running on top of **Unified Ops AX** — a modular monolith architecture that processes a single `Activity` event stream instead of relying on prompt-box interactions:

1. **AS Triage Agent (`as.opened`):** Classifies incoming support tickets, determines severity, and auto-assigns to team members based on workload.
2. **Knowledge Agent (`as.resolved`):** Converts resolved support tickets into structured knowledge documents (drafts) and indexes them into RAG.
3. **Follow-up Agent (`delivery.done`):** Drafts customer follow-up messages — and **can only draft**.
4. **Reconcile Agent (`order.placed`):** Checks the order book against accounting ledgers in a read-only, non-mutating mode.

```
       Business Activity Event Stream (Pub/Sub / Outbox)
                                │
    ┌───────────────────────────┼───────────────────────────┐
    ▼                           ▼                           ▼
┌──────────────┐        ┌──────────────┐        ┌──────────────┐
│  AS Triage   │        │  Knowledge   │        │  Follow-up   │
│  (Auto Assign│        │  (Capture &  │        │ (Draft Only  │
│   Ticket)    │        │  RAG Index)  │        │  No Send)    │
└──────────────┘        └──────────────┘        └──────────────┘
                                                        │
                                                        ▼
                                             ┌──────────────────┐
                                             │  Human Approval  │
                                             │   (HTTP Gate)    │
                                             └─────────┬────────┘
                                                       │
                                                 [409 if missing]
                                                       │
                                                       ▼
                                            HTTP API Send Endpoint
```

---

## 🔒 3 Hard Structural Safety Guarantees

Three guarantees hold regardless of what anyone types or prompt-injects:

1. **Roles are Server-Derived:** No tool accepts a role, identity, or employee ID argument. The LLM has no vocabulary or parameter interface to claim or forge a role. This security guarantee is asserted across tool signatures in automated unit tests.
2. **Retrieval is Filtered in SQL (Security Trimming):** Authorization is separated from ranking. A sales rep asking for the Q3 margin memo receives an empty result set — not a refusal message composed by the LLM, but an empty SQL result generated by `WHERE` clause security trimming before vector similarity ranking.
3. **Nothing Reaches a Customer Unapproved:** The Follow-up agent can queue a draft message and that is the end of its reach. Approving and sending are HTTP endpoints absent from every agent's tool definition. Calling `send()` without human sign-off fails deterministically with an `HTTP 409 Conflict`.

---

## 🏗️ System Architecture: 5-Layer Modular Monolith

Unified Ops AX is organized into 5 decoupled layers backed by a Single Source of Truth (`Activity` event store):

```
L5 Experience       Role-Based Workspaces (app/experience) + Scene Dashboard
L4 Intelligence     4 Governed Agents (app/agents) + Multi-Provider AI Gateway (app/ai)
L3 Hub              Activity Event Store SSOT + Derived Views (app/domain) + RAG Engine (app/rag)
L2 Integration      SaaS Connectors & Orchestration (app/connectors) + Transactional Outbox (app/events)
Governance          Audit Log, Adoption KPIs, Data Ownership (app/governance) + Security Trimming & PII Encryption
```

### Capability & Governance Mapping

| Feature / Requirement | Implementation Location | Security Enforcement |
|---|---|---|
| **Production-Grade RAG** | `app/rag/` (ingest, vectorstore, RAG service) | ACL security trimming in SQL before vector top-k |
| **AI Gateway** | `app/ai/gateway.py` + `app/ai/providers/` | Multi-LLM provider abstraction with fallback |
| **Security Trimming** | `app/security/`, `app/rag/vectorstore.py` | SQL `WHERE` clause filters user `principals` |
| **Enterprise Connectors** | `app/connectors/sharepoint.py`, `graph_client.py` | Microsoft Graph ACL mirroring & fail-closed |
| **SaaS Orchestration** | `app/connectors/{accounting,calendar}.py` | Transferred via outbox with idempotency checks |
| **HITL Human Gate** | `app/agents/followup.py`, `connectors/notify.py` | Human approval HTTP endpoint enforces HTTP 409 |
| **Governance & Audit** | `app/governance/`, `GOVERNANCE.md` | Manager-only RBAC, OpenTelemetry `fleet.access_denied` |
| **MCP Server** | `app/mcp/` | 7 read-only / internal tools exposed via JSON-RPC / stdio |

---

## 🛠️ How We Built It

- **Google Cloud & Vertex AI Stack:**
  - **Gemini 3.5 Flash via Vertex AI**, pinned explicitly to avoid non-deterministic model drift.
  - **Google Agent Developer Kit (ADK):** Configured using the Agent-to-Agent (A2A) template exposing agent capability cards.
  - **Cloud Infrastructure:** Cloud Run (scale-to-zero), Cloud SQL Postgres, Pub/Sub with OIDC push subscriptions, Secret Manager, Model Armor guardrails, Cloud Trace, and Memory Bank Agent Engine.
- **Offline First Engineering Principle:**
  - The entire test suite and full business workflow run completely offline without cloud credentials.
  - SQLite replaces Cloud SQL, and a heuristic guardrail screen replaces Model Armor for local evaluation. All 87 unit tests and 13 E2E verification checks pass locally on a developer laptop.

---

## ⚡ Quick Start

### 1. Prerequisites & Virtual Environment

```bash
# Clone the repository
git clone https://github.com/sechan9999/unified-ops-ax.git
cd unified-ops-ax

# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run Test Suite & E2E Verification

```bash
# Run all 87 offline unit tests
pytest -q

# Run complete E2E smoke verification script (13/13 checks)
python verify.py
```

`verify.py` evaluates the entire workflow in an isolated environment: preflight checks, PII encryption at rest, order-to-accounting reconciliation, event outbox dispatching, RAG loop with security trimming, follow-up HITL approval gate, role-based access control (RLS), governance dashboard authorization, and MCP server JSON-RPC tools.

### 3. Launch Development Server

```bash
uvicorn app.main:app --reload
```
- Interactive API Docs: `http://localhost:8000/docs`
- Role-Based Dashboard: `http://localhost:8000/workspace/dashboard`

---

## 📡 MCP Server (Model Context Protocol)

Expose the business data hub directly to external AI tools (such as Claude Desktop or custom agents) via standard MCP protocols:

```bash
# Launch stdio MCP Server
python -m app.mcp.server

# HTTP Bridge: List available tools
curl http://localhost:8000/mcp/tools

# Call tool via JSON-RPC
curl -X POST http://localhost:8000/mcp/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_pipeline","arguments":{}}}'
```

---

## 💡 Engineering Challenges & Key Learnings

1. **Database Password Redaction:** A database connection error raised with the full connection string URL. We added a centralized `redact()` utility across log handlers to strip credentials and log exception types instead of unformatted tracebacks.
2. **Dual Database Drivers for ADK & Business Code:** ADK session storage runs on SQLAlchemy asyncio (`asyncpg`), whereas business domain logic uses synchronous `pg8000`. We solved driver connection differences by passing socket directories to `asyncpg` and socket file paths to `pg8000`.
3. **Filtering vs. Ranking Separation:** Filtering is security; ranking is quality. Expliciting separating security filtering (SQL `WHERE` predicates) from relevance ranking (vector search) guarantees that security boundaries remain rock-solid regardless of embedding engine changes.
4. **Code is the Contract:** Prompt instructions are courtesies. Hard boundaries enforced in Python, SQL constraints, and API routing guarantee safety even under adversarial prompt injections.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
