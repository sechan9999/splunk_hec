# Plan: inteltrans (Async Multi-Agent Exception Management — Reference Implementation)

> Repo: https://github.com/sechan9999/IntelTrans (local clone: `outputs/IntelTrans`)
> Companion page: `index.html` case study (already committed, e75a9e1) + private artifact
> https://claude.ai/code/artifact/4b09458d-5dfa-42a5-bb38-f326152d8f29

## Goal
Grow the IntelTrans case-study page into a runnable reference implementation:
the FastAPI exception router + async agentic worker from the page as real,
tested Python — runnable locally with zero AWS dependencies — plus the
Terraform modules from section 06 as validate-clean HCL.

## Scope
1. **Ingestion + orchestration app** (`app/`)
   - `app/ingress.py`: `POST /exceptions` → Pydantic validation → structlog
     JSON line → tracked `asyncio.create_task` dispatch → `202 Accepted`
     (design §3 supersedes the original `BackgroundTasks` idea for testability)
   - `app/orchestrator.py`: `asyncio.gather` fan-out (shipment metadata +
     port congestion mocks) → reasoning agent → mitigation write-back
   - `app/guards.py`: idempotency key set (`shipment_id + reported_at`,
     in-memory dict with TTL) and `step_counter` loop guard (max 5 →
     human-review queue list)
   - `app/agents.py`: pluggable reasoning agent — deterministic stub by
     default; optional Bedrock/Claude client behind an env flag (never
     required to run or test)
2. **Tests** (`tests/`, pytest + httpx `AsyncClient`)
   - 202 contract: response returns before workflow completes
   - Duplicate POST suppressed: workflow runs exactly once
   - Concurrency: gather phase wall-time ≈ max(tool latencies), not sum
   - Loop guard: forced parse failure escalates after 5 steps
3. **Terraform** (`infra/`)
   - `modules/queue` (SQS + DLQ redrive), `modules/ecs-service` (reusable
     Fargate service), composition root with `ingestion_api` + `agentic_worker`
     and backlog-per-task autoscaling — matching page section 06
   - `terraform validate` clean; no backend/state, no apply in CI

## Non-goals
- Real AWS deployment or credentials in CI; live Bedrock calls in tests;
  MLflow/Databricks integration; DLQ consumer; Redis (in-memory guard only).

## Success criteria
- `uvicorn app.ingress:app` runs; local `POST /exceptions` p50 < 50 ms
- `pytest` green, including the timing-based concurrency proof
- `terraform -chdir=infra validate` passes
- README updated with run/test instructions; index.html untouched
