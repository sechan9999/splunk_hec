# Completion Report: datahub-eval-loop

- **Feature**: datahub-eval-loop — governance evaluation & regression loop for the
  DataHub-guarded agent platform
- **Period**: 2026-07-22 (single-day cycle)
- **Final Match Rate**: 96% (83% on first check, one Act iteration)
- **Status**: ✅ Completed
- **Target repo**: [sechan9999/splunk_hec_v2](https://github.com/sechan9999/splunk_hec_v2)
  (local clone `outputs/MCPagents-splunk-v2`)
- **Commits**: `60cac0a`, `2e87ccf`, `451c170`, `5229215` — 18 files, +1,437 / −32

---

## 1. Summary

The DataHub guardrail already answered *"should this agent run?"* before execution.
Nothing proved it kept answering **correctly** as the policy changed: the decision
table lived inside a Python function, so a policy change was a code change with no
dedicated gate, and a wrong verdict left no artifact behind.

This cycle wrapped that guardrail in an evaluation and operations loop — the policy
became a reviewable contract, wrong verdicts became permanent fixtures, deploys got
tiered gates, and a BLOCK became a redirect instead of a dead end.

**Headline result**: the loop paid for itself during construction. It surfaced
**four defects that the existing unit tests could not see**, three of them in
behaviour the original design believed was already correct.

---

## 2. PDCA Cycle Trace

| Phase | Artifact | Outcome |
|-------|----------|---------|
| Plan | [datahub-eval-loop.plan.md](../01-plan/features/datahub-eval-loop.plan.md) | 7 scope items derived from a gap analysis against an external field report on operational data agents |
| Design | (skipped — plan carried the design; single-session scope) | — |
| Do | `policies/`, `security/policy.py`, `security/remediation.py`, `tests/`, CI | 18 files |
| Check | [datahub-eval-loop.analysis.md](../03-analysis/datahub-eval-loop.analysis.md) | 83% — 3 findings, one of them a submission-integrity issue |
| Act ×1 | §6 of the analysis | 96% — all 3 findings closed, gate passed |

Origin note: the scope came from comparing this project against a public write-up on
contracts/guards/regression testing for Slack data agents. Concepts were adopted;
that author's operating numbers were deliberately **not** — every figure in this
cycle is measured on this repo.

---

## 3. Deliverables

| Item | Path | Role |
|------|------|------|
| Policy contract | `policies/governance.yaml` | The rules themselves — versioned, CODEOWNERS-reviewed |
| Policy engine | `security/policy.py` | Loader + evaluator; validates rules, rejects unknown predicates |
| Successor suggestion | `security/remediation.py` | Ranked evidence: deprecation note → lineage → naming |
| Golden cases | `tests/golden/*.yaml` | 19 cases, 3 with `origin: real_incident` |
| Regression + gates | `tests/test_golden_cases.py` | 29 checks incl. the coverage gate |
| Structural contracts | `tests/test_audit_contract.py` | 10 checks — accountability must survive refactors |
| Demo consistency | `tests/test_demo_consistency.py` | 8 checks — the demo cannot drift from the engine |
| Headless app smoke | `tests/test_app_smoke.py` | 13 checks — reproducible, replaces an uncitable claim |
| CI gating | `.github/workflows/governance.yml` | Risk-tiered; structural checks block unconditionally |
| Ownership | `.github/CODEOWNERS` | Policy changes need human approval |

### Verified metrics (measured on this repo)

| Metric | Value |
|---|---|
| Test suite | 10 → **70 checks**, ~8s |
| Golden cases | 19 (3 from real incidents) |
| Policy evaluation latency | p50 **0.006 ms** · p95 **0.014 ms** · p99 **0.016 ms** (n=2000) |
| Original tests broken | **0** |

---

## 4. What the loop caught

Each of these was invisible to a suite of ten passing unit tests. This is the
cycle's actual argument for itself.

1. **Masked findings.** `decide()` returned on first match, so a dataset that was
   both deprecated *and* holding unscanned regulated data reported only the
   deprecation — the more serious finding never reached the operator. All matching
   rules now contribute; the most severe verdict wins.
2. **Silent regulated-data access.** A HIPAA read with DLP enabled produced a bare
   `allow` with no reason codes, leaving no trace that regulated data was touched.
   Permitted is not the same as unremarkable; an `informational` rule now records it.
3. **The demo misrepresented the product.** `demo_data.py` shipped a precomputed
   verdict claiming a `warn` the engine would never produce. Caught by replaying the
   demo graph through the live evaluator.
4. **The write-up ran ahead of the screen.** The submission claimed a block "tells
   you where to go instead" and the payload did carry the suggestion — but the UI
   never rendered it, so the one place a judge would look showed nothing. The gap
   between claim and product was a single `st.success` call.

Defects 3 and 4 share a shape the plan never anticipated: **the engine was right and
the surface was stale.** Tests that compare a *representation* against the *engine*
turned out to be the highest-value category in the cycle, and they were not in scope.

---

## 5. Decisions worth keeping

**The policy is data, never code.** Rules may only select among predicates the
evaluator implements, so editing the YAML cannot execute anything and an unknown
predicate is rejected at load. A security component whose config is a config file,
not a plugin point.

**Unknown → open, known-dangerous → closed.** DataHub unreachable still degrades
open, because governance must not become an availability dependency — but it now
says `metadata_unavailable` rather than passing silently. When metadata *is*
readable and says the data is regulated and unscanned, the `catastrophic` tier
refuses to be downgraded.

**A malformed policy raises rather than allowing everything.** A governance layer
that fails open when its own rules will not parse is worse than one that refuses to
start.

**Suggestions carry their basis, confidence, and caveats.** Schema compatibility is
explicitly *not* claimed, because `DatasetContext` has no column metadata and a
guess dressed as a fact is worse than silence.

---

## 6. Intentional deviations from the plan

| Plan said | Shipped | Why |
|---|---|---|
| PII/HIPAA + no DLP → BLOCK | `hipaa/phi/pci` block; generic `pii` stays advisory | Applied literally it would block most useful tables and break an existing test. Splitting the vocabulary keeps the fail-closed story and all 10 original tests. |
| Successor with a schema-match flag | Ranked evidence + `caveats: ["schema compatibility was not checked"]` | No column-level metadata exists to check it with. |

---

## 7. Near-miss worth recording

Externalizing the policy made the guardrail import `yaml`, which was **not** in
`requirements.txt`. Because `_guardrail_preflight` catches every exception and
degrades to allow, the entire governance layer would have silently disabled itself
on Streamlit Cloud while the app looked perfectly healthy. Caught by asking what
the new import meant for deploy, not by any test.

The lesson generalizes: a component that degrades gracefully on failure will also
degrade gracefully on *its own absence*, and that is much harder to notice.

---

## 8. Follow-ups

- The CI workflow is committed and locally validated (YAML parses, the test
  selector resolves to 7 checks) but **has not yet run on GitHub** — the first PR
  after this merge is its real proof.
- The demo's successor resolves via `deprecation_note`; the lineage path is covered
  by golden cases but is still not what a judge sees on screen.
- Drift → PR loop: read *out* of DataHub nightly and open PRs updating the policy
  and its golden cases. The inverse of the write-back that already exists, and the
  half that makes "self-healing" mean something.
- Schema-verified successors, once column metadata is available.
- `docs/live_spike_evidence.md` still records the historical `55/55` AppTest run.
  It is no longer cited as a current guarantee, but if that suite still exists
  somewhere it is worth committing alongside the new one.

---

## 9. Submission impact

The Devpost draft (`docs/devpost_datahub_submission.md` in the target repo) was
updated in step with the code, not after it: a roles table, the policy-contract and
golden-case sections, the successor redirect, measured latency, and a test count
that now comes from a command a reader can run. The one claim that could not be
substantiated from the repository — a 55-check suite whose file was never committed —
was resolved by making it reproducible rather than by quietly restating it.
