# Completion Report: datahub-drift-guard

- **Feature**: datahub-drift-guard — a change → its blast radius → a validated fix
- **Period**: 2026-07-24 (single-day cycle)
- **Final Match Rate**: 99% (94% first check, 2 Act iterations)
- **Status**: ✅ Completed
- **Target repo**: [sechan9999/splunk_hec_v3](https://github.com/sechan9999/splunk_hec_v3)
  (a copy of splunk_hec_v2; local clone `outputs/MCPagents-splunk-v3`)
- **Live**: https://splunkhecv3.streamlit.app/ (Data Context tab → Drift Guard)
- **Commits**: `5f26e1a`, `be6eba1`, `b667ab3`, `0e4d472`, `de6933c` — 11 files, +980/−11
- **Suite**: 74 (copied baseline) → **100 checks**, CI green, validate button verified on the live deploy

---

## 1. Summary

Prompted by KASSI (Splunk hackathon grand prize) — a commit-time loop that
doesn't just detect a regression but pinpoints the cause and hands a validated
fix, with the verdict computed deterministically. We took the *shape*, not the
domain: KASSI's ground truth is Splunk telemetry + statistical ML; ours is
**DataHub lineage**, the natural causal graph for governance drift.

A synthetic change now traces through lineage to its blast radius (which
downstream assets it reaches, which policy rule it trips, whom to notify), and a
change that trips a rule becomes a golden case that is **validated against the
suite before it is surfaced** — the drift → PR loop this project named in its own
What's-next, now working and deployed.

Built in a fresh **v3 repo copied from v2**, so the v2 hackathon submission stays
untouched.

---

## 2. PDCA Cycle Trace

| Phase | Artifact | Outcome |
|-------|----------|---------|
| Plan | [datahub-drift-guard.plan.md](../01-plan/features/datahub-drift-guard.plan.md) | 9 scope items, B-then-A sequencing, honest boundaries vs KASSI |
| Design | (skipped — plan carried it; single-session scope) | — |
| Do | `security/drift.py`, `security/fix.py`, `tests/`, CI, UI | Milestone B (`5f26e1a`) then A (`be6eba1`) |
| Check | [datahub-drift-guard.analysis.md](../03-analysis/datahub-drift-guard.analysis.md) | 94% — 2 real findings + 2 deliberate deviations |
| Act ×1 | analysis §6 | 94 → 99%: successor wiring + in-process fallback |
| Act ×2 | analysis §7 | Cloud false-reject bug, found by deploying and clicking |

---

## 3. Deliverables

| Item | Path |
|------|------|
| Blast radius from lineage (bidirectional, multi-hop) | `security/drift.py` |
| Fix generation + validate-before-surface + groundedness | `security/fix.py` |
| Drift scenarios (regression contract) | `tests/drift/scenarios.yaml` (6) |
| Milestone-B tests | `tests/test_drift.py` (13) |
| Milestone-A tests | `tests/test_fix.py` (12) |
| CI drift job | `.github/workflows/governance.yml` |
| Drift Guard UI (report + proposed fix + validate button) | `demo_app.py` |

### Verified metrics (own, small, reproducible)

| Metric | Value |
|---|---|
| Test suite | 74 (copied) → **100**, CI green |
| Drift scenarios / blast-radius accuracy | 6 / **6-of-6** |
| Codifiable change kinds / fixes that validate | 3 / **3-of-3** green |
| Corrupted fix | **1 rejected** (the gate bites) |
| False alarms on the healthy control | **0** |
| Successor evidence paths demonstrated | note (high) · lineage (medium) · none |

---

## 4. What the loop is, in one line each

- **Blast radius from lineage**: `llm_costs` deprecate reaches `router_model` an
  ML model *two hops* away, names the `deprecated_dataset` rule it trips, and
  lists both owners — computed from the graph, so it cannot cite an asset the
  graph does not contain (a groundedness test enforces this).
- **Validated fix**: the change becomes a golden case, written into a scratch
  copy of the suite; only a case the engine actually produces is surfaced.
  Semantic validation, not syntactic — the governance analog of "apply, then
  re-parse to confirm it compiles".
- **A block that redirects**: a deprecation also says where consumers migrate,
  from the deprecation note or inferred from lineage, with the confidence that
  reflects which — reusing the shipped remediation.

---

## 5. What deploying caught that tests could not

The single most instructive moment of the cycle. After deploying v3 and clicking
the validate button on the **live app**, a perfectly valid fix returned
**Rejected**. Cause: the Streamlit Cloud runtime installs `requirements.txt`,
which has no pytest, so the validation subprocess exited non-zero — and the
first fallback only caught "cannot spawn", not "spawned and failed for an infra
reason". A missing test framework was being reported as "your fix is wrong".

AppTest never saw it (it runs locally, with pytest present). Only driving the
deployed app surfaced it. Fixed by distinguishing an infra failure from a real
test failure and falling back to the in-process check; re-verified by clicking
the button on the live app, which now returns *"Validated — in-process: got
block/['deprecated_dataset'], expected block/['deprecated_dataset']"*.

This is the same lesson the whole project keeps relearning: **a feature is not
"done" until it has been exercised on the runtime it will actually run on.**

---

## 6. Intentional deviations

| Plan said | What happened | Why |
|---|---|---|
| Fix generation: 3 flavors | Golden-case + successor shipped; policy-edit-for-missing-reference deferred | No demo scenario, not load-bearing (Scope 5 scored 95%) |
| Devpost What's-next updated | Not updated | v3 is a separate private repo, not the live v2 submission — updating it would describe a feature absent from the submitted repo |

---

## 7. Lessons

- **Lineage is a real RCA engine.** Pointing KASSI's "pinpoint via the graph"
  idea at DataHub's lineage graph needed no ML — the graph *is* the causal
  chain, and bidirectional traversal recovered a multi-hop reach the
  hand-authored graph's one-sided lists hid.
- **"Validated" only means something if the gate can fail.** The corruption test
  — feed the validator a wrong verdict, require rejection — is what makes the
  loop trustworthy, and it earned its keep in the Cloud bug (where the gate was
  failing for the *wrong* reason).
- **Deploy before you claim.** Findings 2 and 5 were both about the validate
  button, and neither closed until the app was on Streamlit Cloud and clicked.

---

## 8. Follow-ups

- Wire the policy-edit fix flavor (deferred) when a demo scenario justifies it.
- Real `git diff` / dbt-manifest trigger in place of the synthetic `ChangeEvent`.
- If v3 ever becomes a submission, the Devpost update belongs to that moment.
- `/pdca archive datahub-drift-guard --summary`.
