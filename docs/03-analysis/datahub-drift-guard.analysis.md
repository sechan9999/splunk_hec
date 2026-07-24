# Gap Analysis: datahub-drift-guard

- **Feature**: datahub-drift-guard (blast radius → validated fix)
- **Analyzed**: 2026-07-24
- **Baseline**: [plan](../01-plan/features/datahub-drift-guard.plan.md) — no design
  doc this cycle, so the plan's Scope (steps 1–9) and Success criteria are the
  contract measured against.
- **Implementation**: `sechan9999/splunk_hec_v3` @ `be6eba1`
  (`5f26e1a` Milestone B, `be6eba1` Milestone A)
- **Match Rate**: **94%**
- **Verdict**: above the 90% gate. Both milestones landed; the residual is two
  secondary fix flavors that were deferred, and a deliberate Devpost non-update.

---

## 1. Scope coverage

| # | Scope item | Status | Score |
|---|---|---|---|
| 1 | Synthetic change manifest (`ChangeEvent`, fixtures) | Complete — 6 scenarios | 100% |
| 2 | Blast radius via lineage (transitive, terminal leaves) | Complete, **exceeds** plan (bidirectional) | 100% |
| 3 | Report object + Streamlit rendering | Complete | 100% |
| 4 | Milestone-B tests | Complete — 13 checks | 100% |
| 5 | Fix generation | Partial — golden-case path only | 70% |
| 6 | Validate before surfacing | Complete — hermetic, semantic | 100% |
| 7 | Groundedness guard | Complete | 100% |
| 8 | CI drift job | Complete — **green on GitHub** | 100% |
| 9 | Docs + submission | Partial — README done, Devpost deliberate skip | 80% |

Mean 94%. B (1–4) and A's core loop (6–8) are all complete; the gap is
concentrated in step 5 and the Devpost half of step 9.

---

## 2. Success criteria

| Criterion | Result |
|---|---|
| `blast_radius` deterministic and correct on every fixture | **Met** — 6/6, plus a determinism test |
| ≥1 `deprecate` scenario produces a fix that passes `pytest` end to end, in CI | **Met** — drift job green on master (run 30090930677) runs propose→validate |
| Negative control → empty blast radius (no false alarm) | **Met** — `cosmetic` control |
| Existing 74 checks still green, layer env-gated | **Met** — 96 total, originals intact |
| Measured, own numbers recorded | **Met** — 6/6 blast, 3/3 fixes validate, 1 corrupted rejected, 0 false alarms |

All five success criteria met.

---

## 3. Findings

### Finding 1 — Fix generation covers only the golden-case path (Scope 5)

The plan named three fix flavors: (a) a golden case for a change that trips a
rule, (b) surfacing the successor when a downstream now points at a deprecated
upstream, (c) a `policies/` edit when a rule references a dataset/tag that no
longer exists. Only **(a)** shipped, for the three codifiable kinds
(deprecate, retag_sensitive, break_quality).

This is the right 80/20 — (a) is the drift→PR loop and the KASSI-shaped
differentiator, and it is fully validated. But the report should not imply the
other two exist. (b) already exists as `remediation.suggest_successor` and is
merely un-wired into `propose_fix`; (c) is unbuilt. Neither is load-bearing for
the demo.

**Fix if pursued**: wire `suggest_successor` into `propose_fix` for the
deprecate-with-successor case (small); defer (c).

### Finding 2 — The validate button spawns a pytest subprocess; unverified on Streamlit Cloud

`validate_fix` runs `python -m pytest` in a subprocess. That is verified locally
and in CI, but the **UI "Validate" button** would spawn that subprocess *inside
the Streamlit Cloud container*, which may be sandboxed, slow, or unable to spawn
child processes. AppTest runs locally so it did not exercise the deployed path.

This matters because the button is where a judge would see validation happen
live. Untested on the actual runtime.

**Fix if pursued**: after deploying v3, click the button on the live app; if the
subprocess is blocked, fall back to the in-process equivalent (build the
`DatasetContext` from the generated case and call `decide` directly — same
semantic check, no child process). The CI/test path stays as the authoritative
proof regardless.

### Finding 3 — Devpost not updated (deliberate deviation from Scope 9)

The plan said "Devpost What's-next updated". It was **not**, on purpose: the live
Devpost is the v2 submission, and v3 is a separate private repo. Describing a
feature that does not exist in the submitted repo on the submission page would
be exactly the claim-ahead-of-product problem this project keeps catching. The
README (in v3) is updated; the measured numbers are recorded there. If v3
becomes a submission, the Devpost update belongs to that moment.

### Finding 4 — v3 is not deployed (out of scope, noted for the demo)

The drift guard is only visible via local `streamlit run` today. Not a plan
gap (deployment was never in scope), but the demo story is incomplete until v3
is connected to Streamlit Cloud. Ties to Finding 2 — deploying is also what
would let the validate button be verified.

---

## 4. Work that exceeded the plan

- **Bidirectional lineage** (Scope 2): the demo graph's `downstream`/`upstream`
  lists disagree, so a naive downstream walk misses the
  `llm_costs → user_features_v1 → router_model` chain. Computing consumers as
  `declared downstream ∪ reverse-upstream` is both more correct and what
  surfaces the multi-hop reach to an ML model — the headline scenario.
- **Corruption test** (`test_a_wrong_fix_is_rejected`): not named in the plan,
  but it is what makes "validated" mean anything — a gate that never fails is
  decoration. This is the single most important test in the milestone.
- **Hermetic validation** via a `GOLDEN_DIR` override: the fix is validated
  against a scratch copy, never mutating the real suite.

---

## 5. Recommendation

At 94% the cycle clears the gate; the two real gaps (Findings 1–2) are small and
neither blocks the demo. Suggested order if iterating: Finding 2 first (it is the
one a judge would hit — verify or add the in-process fallback), then Finding 1(b)
(wire the successor fix, cheap). Finding 3 is correct as-is; Finding 4 is a
deploy step, not code.

Ready for `/pdca report datahub-drift-guard`, or one short Act iteration to close
Findings 1–2 first.
