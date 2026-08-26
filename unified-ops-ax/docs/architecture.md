# Unified Ops AX & Gemini Ops Fleet — Architecture

This document details the three core architectural views of **Unified Ops AX** and **Gemini Ops Fleet**:
1. **System Map:** Cloud Run microservices, Vertex AI, Google ADK, and infrastructure components.
2. **Safety Authorization Path:** Deterministic code-enforced security boundaries (SQL trimming, zero-trust tools, HTTP 409 human gate).
3. **Asynchronous Event-Driven Pipeline:** Event outbox, Pub/Sub trigger, and automated agent dispatching.

---

## 1. System Map

```mermaid
flowchart TB
    subgraph ClientLayer["Clients & API Callers"]
        emp["Employee Web UI / Dashboard<br/>X-Fleet-Token / Bearer"]
        ps["Google Cloud Pub/Sub<br/>Push Subscription"]
        mcp["External AI Tools / Claude<br/>MCP JSON-RPC / stdio"]
    end

    subgraph ServiceLayer["Cloud Run · Unified Ops AX Engine"]
        api["FastAPI App Core<br/>/workspace · /hub · /governance"]
        a2a["A2A Agent Card<br/>/.well-known/agent.json"]
        guard["BasePlugin Guardrail<br/>Model Armor + Heuristic Screen"]
        
        subgraph Agents["Governed Agent Fleet"]
            tri["AS Triage Agent<br/>(Auto Assign)"]
            kno["Knowledge Agent<br/>(Capture & Index)"]
            fol["Follow-up Agent<br/>(Draft Only)"]
            rec["Reconcile Agent<br/>(Read Only)"]
        end
        
        worker["Event Worker<br/>Outbox Poller"]
    end

    subgraph InfraLayer["Google Cloud Platform"]
        gemini["Vertex AI<br/>Gemini 3.5 Flash"]
        sql[("Cloud SQL Postgres<br/>fleet data + ADK sessions")]
        armor["Model Armor<br/>Safety Plugin"]
        trace["Cloud Trace / OpenTelemetry<br/>fleet.access_denied Spans"]
    end

    emp --> api
    ps --> api
    mcp --> api
    api --> a2a
    api --> guard
    guard --> Agents
    Agents --> gemini
    guard -. screens .-> armor
    Agents --> sql
    worker --> sql
    api --> trace
```

---

## 2. Safety Authorization Path (The 3 Hard Guarantees)

Every security boundary is enforced in Python and SQL code before or during execution.

```mermaid
flowchart TD
    req["Incoming HTTP Request / Event Trigger"] --> auth

    subgraph ServerSide["1. Identity & Role Resolution"]
        auth["Resolve identity from Bearer token<br/>Role derived on server (no role arg)"]
        guard_check{"Model Armor Guardrail:<br/>Prompt Injection or PII?"}
    end

    auth --> guard_check
    guard_check -->|Blocked| stop_guard["Refusal: 400 Bad Request<br/>fleet.guardrail_blocked = true"]
    guard_check -->|Clean| llm_call["Gemini 3.5 Flash<br/>Generates Tool Call"]

    subgraph ToolACL["2. Zero-Trust Tool Execution"]
        acl_check{"May caller's role<br/>invoke target tool?"}
        sql_trim["SQL Security Trimming:<br/>WHERE acl && :user_principals"]
    end

    llm_call --> acl_check
    acl_check -->|Denied| stop_acl["Refusal: 403 Forbidden<br/>fleet.access_denied = true"]
    acl_check -->|Allowed| sql_trim
    sql_trim --> db_result["Permitted Rows Returned Only<br/>(Filtered before Vector Ranking)"]

    subgraph HumanGate["3. External Messaging Boundary"]
        hitl_check{"Is action an external<br/>customer message send?"}
        http_gate{"Human Signed Off?<br/>POST /agents/followup/{id}/approve"}
    end

    db_result --> hitl_check
    hitl_check -->|No (Internal Action)| complete["Action Executed Successfully"]
    hitl_check -->|Yes (External Email)| http_gate
    http_gate -->|Not Approved| stop_hitl["Refusal: HTTP 409 Conflict<br/>Approval Required"]
    http_gate -->|Approved| send_msg["Notifier Adapter Sends Message<br/>source=app (Human Action)"]
```

---

## 3. Asynchronous Event Stream Pipeline

Business operations write `Activity` events in the same database transaction, which are dispatched asynchronously to trigger agent workflows.

```mermaid
sequenceDiagram
    autonumber
    actor User as Employee / Customer
    participant App as FastAPI Core
    participant DB as Cloud SQL Postgres (Activity SSOT)
    participant Worker as Outbox Worker / Pub/Sub
    participant Fleet as Agent Fleet (Triage/Knowledge/Follow-up)
    participant Human as Human Supervisor

    User->>App: POST /hub/orders (Place Order)
    App->>DB: Write Order + ProductionJob + Activity(order.placed) [In Single Transaction]
    DB-->>App: Transaction Committed
    
    loop Interval / Push Trigger
        Worker->>DB: Poll Pending Outbox Activity Events
        Worker->>Fleet: Dispatch Event (e.g. delivery.done)
    end
    
    Fleet->>DB: Draft Customer Follow-up (Status=draft)
    Fleet->>DB: Emit Activity(followup.drafted) [source=agent]
    
    Note over Fleet,Human: Agent execution stops here. Follow-up is queued as draft.
    
    Human->>App: Review Draft in HITL Queue UI
    Human->>App: POST /agents/followup/{id}/approve
    App->>DB: Update Status=sent, Emit Activity(followup.sent) [source=app]
    App-->>User: Customer Notified via Notifier Adapter
```
