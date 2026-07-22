# Gap Analysis: datahub-eval-loop

- **Feature**: datahub-eval-loop
- **Analyzed**: 2026-07-22
- **Baseline**: [ds plan](../01-plan/features/datahub-eval-loop.plan.md) — no design
  document exists for this cycle, so the plan's Scope and Success criteria are
  the contract being measured against.
- **Implementation**: `sechan9999/splunk_hec_v2` @ `451c170`
  (`60cac0a` policy+golden, `2e87ccf` remediation+demo gate, `451c170` docs)
- **Match Rate**: **83%** → **96%** after Act iteration 1 (see §6)
- **Verdict**: initial pass fell below the 90% gate — two scope items were
  genuinely incomplete (CI gating, evidence bundle shape) and one plan
  assumption turned out to be wrong on contact. All three findings are now
  closed; §6 records the re-check.

---

## 1. Scope coverage

| # | Scope item | Status | Score |
|---|---|---|---|
| 1 | Policy as versioned contract | Complete | 100% |
| 2 | Severity re-tiering | Complete, narrowed on purpose | 90% |
| 3 | Golden case suite + coverage gate | Complete | 100% |
| 4 | Structured verdict payload + evidence bundle | Partial | 60% |
| 5 | Lineage-backed remediation | Complete, one claim dropped | 85% |
| 6 | Risk-tiered deploy gating (CI) | Not started | 0% |
| 7 | Documentation & submission update | Complete | 100% |

Unweighted mean: **76%**. Weighting by the plan's own sequencing (items 1, 3, 7
were declared the priority and are all complete; item 6 was explicitly flagged
as deferrable) gives **83%**, which is the figure recorded above.

---

## 2. Success criteria

| Criterion | Result |
|---|---|
| Policy is the only source of rules; no rule literals in code; loader tested | **Met** — grep over `governance_bridge.py` finds no rule literals; 5 loader tests |
| Golden suite green with coverage gate enforced, demonstrated by a failing probe | **Met** — throwaway rule produced `policy reason codes with no golden case: ['throwaway_probe_code']` |
| HIPAA + unscanned returns BLOCK; DataHub-unreachable returns ALLOW with `metadata_unavailable` | **Met** — both are golden cases |
| ≥1 demo scenario where a deprecated BLOCK carries a lineage-derived successor | **Partial** — the demo scenario (`user_events_v1`) resolves via `deprecation_note`, not lineage. The lineage path is covered by golden cases but is not what a judge sees in the demo. |
| Existing 55 checks still pass | **Cannot verify** — see Finding 3 |
| Measured numbers recorded | **Met** — p50 0.006 ms / p95 0.014 ms / p99 0.016 ms (n=2000) in README and Devpost draft |

---

## 3. Findings

### Finding 1 — Evidence bundle was specified but only half-built (Scope 4)

The plan called for a named, self-contained `evidence{urn, tags_consulted,
quality_state, checked_at}` sub-object. What shipped carries the same
*information* — the verdict embeds `context.to_dict()` — but not in that shape,
and `fetched_at` is absent from `to_dict()` entirely, so a verdict cannot say
how stale the metadata behind it was. With a 5-minute cache that is a real
audit weakness: a block and the metadata that justified it can be up to five
minutes apart with nothing recording the gap.

**Fix**: add `fetched_at` to `DatasetContext.to_dict()` and reshape the verdict
payload to the planned `evidence` block. Small, contained.

### Finding 2 — CI gating not wired (Scope 6)

`.github/CODEOWNERS` exists, so policy changes require review, but there are no
workflows: nothing enforces "policy change must clear the golden suite" or the
unconditional structural block on removing the audit write-back. The gates are
described in the README and Devpost as design intent, which is accurate as
written, but the plan asked for them to run.

**Fix**: one `.github/workflows/governance.yml` with path filters. The suite it
would call already exists and passes, so this is wiring, not new logic.

### Finding 3 — The "55-check AppTest suite" is not reproducible from the repo

The Devpost and README both cite a 55-check headless suite, and
`docs/live_spike_evidence.md` records `55/55`. **The test file is not in the
repository** — no `AppTest` reference exists in any committed `.py`. The claim
is presumably true of the machine it ran on, but nobody, including a judge, can
reproduce it, and the plan's "existing 55 checks still pass" criterion is
therefore unverifiable rather than met.

What was verified instead: `AppTest.from_file("demo_app.py")` renders with
`exception: ElementList()` and 7 tabs after the `demo_data.py` and policy
changes. The Devpost claim was rewritten to say exactly that, which is
defensible, rather than repeating an unreproducible number.

**Fix**: commit the AppTest suite, or drop the 55-check claim everywhere.
This one matters beyond the score — an unbacked number in a submission is the
kind of thing a jury checks.

### Finding 4 — A plan assumption was wrong, and the deviation is the right call

The plan said PII/HIPAA-tagged + no DLP should move from WARN to BLOCK. Applied
literally that breaks `test_pii_with_dlp_off_warns` and, worse, would block on
any `pii` tag — which in this catalog covers most useful tables. What shipped
splits the vocabulary: `hipaa/phi/pci` are catastrophic and block; generic `pii`
stays advisory. This preserves all ten original tests and still delivers the
fail-closed story. Recorded as an intentional deviation, not a gap.

Similarly, the plan's "successor with a schema-match flag" was dropped:
`DatasetContext` has no column-level metadata, so a compatibility claim would
have been a guess presented as a fact. Suggestions now carry an explicit
`caveats: ["successor is unverified: schema compatibility was not checked"]`.
Honest, and the follow-up is named in What's Next.

### Finding 5 — Two governance bugs surfaced that were not in the plan at all

Neither was anticipated; both were found by building the evaluation loop, which
is the strongest available evidence that the loop was worth building.

1. **Masked findings.** The original `decide()` returned on first match, so a
   dataset that was both deprecated *and* holding unscanned regulated data
   reported only the deprecation. The more serious finding never reached the
   operator. Now all matching rules contribute and the most severe verdict wins.
2. **Silent regulated-data access.** A HIPAA read with DLP enabled produced a
   bare `allow` with no reason codes — a regulated-data access leaving no trace
   in the audit log. Fixed with an `informational` rule so permitted access is
   still recorded.

Both are golden cases with `origin: real_incident`.

### Finding 6 — The demo was misrepresenting the product

`demo_data.py` shipped a precomputed verdict for `patients_pii` claiming `warn`
that the live engine would never produce. Caught by replaying the demo graph
through the evaluator; `tests/test_demo_consistency.py` now makes that drift
impossible. Not in the plan, and arguably the highest-value single test in the
repo given that the demo *is* the submission for most judges.

---

## 4. Unplanned work that shipped

- PyYAML added to `requirements.txt`. Without it the guardrail import fails, and
  because `_guardrail_preflight` catches every exception and degrades to allow,
  **the entire governance layer would have silently disabled itself on Streamlit
  Cloud** while looking healthy. This was a deploy-breaking omission introduced
  by the policy work itself.
- `tests/test_demo_consistency.py` (Finding 6).
- `sensitive_access_logged` informational rule (Finding 5.2).
- `deprecation_note` plumbed through `DatasetContext` and the GraphQL query.

---

## 5. Recommendation

Two of the three gaps are small and mechanical (Findings 1 and 2). Finding 3 is
not mechanical — it is a claim in a public submission that the repository cannot
substantiate, and it should be resolved before the submission is finalized
regardless of what the match rate says.

Suggested order: Finding 3 (submission integrity) → Finding 2 (CI wiring, the
suite already exists) → Finding 1 (evidence shape). All three together are well
under a day and would put the cycle above the 90% gate.

---

## 6. Act iteration 1 — re-check

- **Date**: 2026-07-22
- **Commit**: `5229215`
- **Match Rate**: 83% → **96%**
- **Suite**: 47 → **70 checks**, all green in ~8s

| # | Scope item | Before | After |
|---|---|---|---|
| 1 | Policy as versioned contract | 100% | 100% |
| 2 | Severity re-tiering | 90% | 90% (deviation stands, see Finding 4) |
| 3 | Golden case suite + coverage gate | 100% | 100% |
| 4 | Structured verdict payload + evidence bundle | 60% | **100%** |
| 5 | Lineage-backed remediation | 85% | **95%** |
| 6 | Risk-tiered deploy gating (CI) | 0% | **95%** |
| 7 | Documentation & submission update | 100% | 100% |

### What closed

**Finding 1 — evidence bundle.** Verdicts now carry a named `evidence` block
(`urn`, `tags_consulted`, `quality_state`, `deprecated`, `checked_at`,
`metadata_age_sec`), and `fetched_at` reaches `DatasetContext.to_dict()`. The
staleness gap the analysis called out is now measured rather than invisible:
`test_evidence_records_metadata_staleness` proves a verdict resting on
two-minute-old metadata reports exactly that.

**Finding 2 — CI gating.** `.github/workflows/governance.yml` implements the
planned tiering. Structural audit contracts run first and block unconditionally;
a diff touching `policies/` or `security/policy.py` additionally runs the
coverage gate and emits a CODEOWNERS reminder. `tests/test_audit_contract.py`
(10 checks) turns "the audit trail must survive refactors" into something a
machine enforces — including that the local trail outlives a dead GMS, and that
`GUARDRAIL_MODE=off` can never be mistaken for a clean allow.

**Finding 3 — the unreproducible 55.** Resolved by making it reproducible
rather than by deleting the claim: `tests/test_app_smoke.py` (13 checks) is
committed, and every count in the README and Devpost draft now comes from
`pytest tests -q` on a clean checkout. The historical `55/55` note stays in
`live_spike_evidence.md` as a record of that session, but is no longer cited as
a current guarantee.

### Found while fixing — the demo was behind the write-up

The Devpost draft claimed a block "tells you where to go instead", and the
payload did carry the suggestion — but `demo_app.py` never rendered it, so the
one place a judge would look showed nothing. The claim was ahead of the product
by a single `st.success` call. Now the Data Context tab shows the successor
with its basis, confidence, and caveats, and says so explicitly when no
successor can be justified. Two AppTest checks pin both branches.

This is the same class of defect as Finding 6 in the original analysis: the
engine was right and the surface was stale. Worth noting that both were caught
by tests that compare a *representation* against the *engine*, which is a
category the original plan did not anticipate at all.

### Remaining (not blocking)

- **Scope 2 (90%)**: `pii` stays advisory while `hipaa/phi/pci` block. Recorded
  as an intentional deviation in Finding 4, not a defect.
- **Scope 5 (95% → 100%)**: closed by `5a84157`. `session_metrics_v1` puts the
  lineage path on screen. Schema verification remains explicitly out of scope
  and caveated in the payload.
- **Scope 6 (95% → 100%)**: closed. The claim that the workflow "has not yet
  run on GitHub" was wrong when written — the `5229215` push had already
  triggered it successfully. PR #1 then verified the `pull_request` trigger and
  path filters end to end.

> Both residuals were closed the same day. The lesson from the first one is
> worth keeping: an unverified status claim in an analysis document is the same
> defect class the cycle set out to fix, just aimed at ourselves.

**Gate**: 96% ≥ 90%. Ready for `/pdca report datahub-eval-loop`.
