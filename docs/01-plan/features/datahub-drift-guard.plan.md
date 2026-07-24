# Plan: datahub-drift-guard (Governance Drift → Validated Fix Loop)

> Target repo: https://github.com/sechan9999/splunk_hec_v2 — clone at
> `outputs/MCPagents-splunk-v2`. Plan stored here for PDCA continuity.
> Builds directly on the archived [[datahub-eval-loop]] cycle (policy contract,
> golden suite, lineage remediation, CI gating — all already shipped).
> Ships the "drift → PR loop" item this project already named in its own
> "What's next", now as a working feature.

## Origin & honest framing

Prompted by KASSI (Splunk Agentic Ops Hackathon grand prize): a commit-time
loop that doesn't just *detect* a performance regression but pinpoints the cause
and hands a validated fix, with the verdict computed **deterministically** so a
run cannot pass on a hallucinated analysis.

We adopt the *shape*, not the domain. KASSI's ground truth is Splunk
telemetry + statistical ML; ours is **DataHub lineage** — the natural causal
graph for governance drift. We deliberately do **not** chase KASSI's depth
(real load, ML RCA, large benchmarks): different hackathon, different home turf,
and matching it in the time we have would be hollow. Every number we publish
must be one we measured on this repo — small N, labeled, reproducible. The
demo runs on the simulated catalog; the live GraphQL path stays env-gated.

## Problem

A dbt/SQL change lands and silently breaks a governance contract: it deprecates
a table three dashboards depend on, drops a column a policy rule keys on, or
points a consumer at a now-deprecated upstream. Today nothing connects "this
diff" to "these downstream assets, this policy rule, these owners" — and nothing
turns that into a fix the existing test suite has already validated.

## What already exists (reused, not rebuilt)

- `tools/datahub_mcp_tool.py` — `DatasetContext` with `upstream`/`downstream`
  URN lists; `demo_data.gen_datahub_context()` is the simulated graph (7
  datasets; downstream leaves include consumer dashboards/models, not just
  datasets).
- `security/policy.py` + `policies/governance.yaml` — the verdict engine.
- `security/remediation.py` — successor suggestion (already walks lineage).
- `tests/` — golden suite + coverage gate + demo-consistency + app smoke (74).
- `.github/workflows/governance.yml` — risk-tiered CI.

## Scope

### Milestone B — blast-radius report (first, safe, demoable)

1. **Synthetic change manifest** (`security/drift.py`)
   - Input shape (no real git parsing this cycle):
     `ChangeEvent(dataset, kind, detail)` where `kind ∈
     {deprecate, drop_column, retag_sensitive, drop_owner, break_quality}`.
   - A small fixture set of realistic scenarios against the demo graph.
2. **Blast radius via lineage** (`security/drift.py::blast_radius`)
   - Walk `downstream` transitively from the changed dataset (BFS over the
     graph; terminal consumers like `traffic_dashboard`/`router_model` are
     leaves). Deterministic, computed from the graph — the whole thesis.
   - Return, per change: affected downstream assets (with depth), the policy
     `reason_code`(s) it would newly trigger (by re-running `evaluate` on the
     post-change context), and the owners to notify.
3. **Report object + rendering**
   - `DriftReport{change, affected[], implicated_rules[], owners[],
     severity}` with a `to_dict()` — self-contained, no DataHub round-trip.
   - New Streamlit sub-section in the Data Context tab: pick a scenario →
     see the blast radius as a small lineage list + implicated rules + owners.
4. **Tests** — golden-style drift fixtures asserting the blast radius
   (affected set, implicated codes, owners) per scenario; a determinism test
   (same input → same report); a "consumer is not a dataset" guard.

### Milestone A — validated fix (adds the KASSI differentiator)

5. **Fix generation** (`security/drift.py::propose_fix`)
   - Per drift kind, emit a concrete diff to `policies/governance.yaml` and/or
     `tests/golden/*.yaml`:
     - `deprecate` → add the golden case + any policy fixture for the newly
       deprecated dataset (this *is* the drift→PR loop).
     - downstream now on a deprecated upstream → surface the successor
       (reuse `remediation.suggest_successor`).
     - policy references a dataset/tag that no longer exists → propose the
       policy edit.
   - Fixes are advisory, never auto-committed.
6. **Validate before surfacing** (`security/drift.py::validate_fix`)
   - Apply the proposed diff to a scratch copy, run `pytest tests -q`
     (golden suite + coverage gate) in a subprocess, and **only surface the
     fix if green**. Our analog of KASSI's "apply + reparse" — but *semantic*
     (tests pass) rather than syntactic (compiles).
7. **Groundedness guard**
   - Any natural-language explanation attached to a report may only cite
     datasets/owners present in the lineage result; reject (and log) otherwise.
     Deterministic check, no second model required for the MVP.
8. **CI job** (`.github/workflows/governance.yml`)
   - A `drift` job: given a scenario fixture, run the loop and fail if a
     proposed fix does not pass validation, or if the report cites an asset
     absent from the graph.
9. **Docs + submission**
   - README "drift → PR loop" moves from *What's next* to *shipped*; Devpost
     "What's next" updated; measured numbers recorded.

## Non-goals (this cycle)

Real `git diff` / dbt manifest parsing (synthetic input only); transitive
lineage beyond the demo graph's depth; auto-opening real PRs; a second
auditor model; statistical/ML root-cause (lineage is our RCA engine, on
purpose).

## Success criteria

- `blast_radius` is deterministic and correct on every drift fixture:
  affected downstream set, implicated `reason_code`s, and owners all match the
  hand-checked expectation (asserted in tests).
- At least one scenario where a `deprecate` change produces a **fix that
  passes `pytest tests`** end to end, demonstrated in CI.
- A negative control: a change with no downstream impact yields an empty
  blast radius (no false alarm) — mirrors KASSI's "0% false alarms on healthy
  controls", measured on our own fixtures.
- Existing 74 checks still green; DataHub layer stays env-gated.
- Recorded, our own numbers: # drift fixtures, blast-radius accuracy
  (correct/total), # proposed fixes that pass validation, false-alarm rate on
  no-impact controls.

## Sequencing

B first (steps 1–4): a demoable blast-radius report with zero risk to the
current submission. Then A (5–8) adds the validated-fix loop, which is the
KASSI-shaped differentiator and where our semantic validation beats a syntactic
one. Step 9 last — and only claim what actually runs.
