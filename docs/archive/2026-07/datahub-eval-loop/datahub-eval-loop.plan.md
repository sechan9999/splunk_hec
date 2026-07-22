# Plan: datahub-eval-loop (Governance Evaluation & Regression Loop)

> Target repo: https://github.com/sechan9999/splunk_hec_v2 — **not cloned in this
> session**; plan stored here for PDCA continuity, implementation must run from
> a v2 checkout.
> Submission: https://devpost.com/software/agentic-ops-control-center-datahub-guarded-ai-agents
> Live demo: https://splunkhec2.streamlit.app/
> Source of the idea: gap analysis vs. Seowoo Han's "Slack 질문 500건을 처리하는
> Data Agent" article (contracts / guards / regression evaluation). Concepts are
> industry patterns and fair to adopt; that article's operating numbers are its
> own and must never appear in our submission.

## Problem

The DataHub guardrail today answers *"should this agent run?"* at execution time,
but nothing proves the guardrail keeps answering **correctly** as the policy
changes. The decision table lives inside Python, so a policy change is a code
change with no dedicated regression gate, and a wrong verdict leaves no artifact
behind. That is the difference between a working demo and an operable product —
and it is the gap a governance-themed jury will probe first.

## Goal

Wrap the existing pre-flight guardrail in an evaluation and operations loop:
externalize the policy into a reviewable versioned contract, make every wrong
verdict a permanent golden case, gate deploys on that suite, and turn a BLOCK
from a dead end into an actionable remediation.

## Scope

1. **Policy as a versioned contract** (`policies/governance.yaml`)
   - Lift the decision table out of Python into ordered YAML rules: match
     condition (tag / quality state / DLP state), `verdict`, `severity_tier`,
     stable `reason_code`, owner-notification flag.
   - Three severity tiers: `catastrophic` → BLOCK (fail-closed),
     `serious` → WARN + proceed, `informational` → log only.
   - Top-level `version` string, stamped into every verdict payload.
   - CODEOWNERS entry so policy edits require human approval — the governance
     policy is itself governed.
   - Decision function keeps its pure signature, now `(metadata, policy) →
     verdict`; **zero hardcoded rules remain in code** (grep-verifiable).

2. **Severity re-tiering (a policy change, visible as a diff)**
   - `PII/HIPAA-tagged + no DLP scan` moves WARN → **BLOCK** under
     `catastrophic`: if we can read the metadata and it says the data is
     sensitive, we close.
   - `DataHub unreachable` **stays degrade-open** (ALLOW) but gets its own
     `reason_code: metadata_unavailable` — we cannot classify what we cannot
     read, and availability must not depend on the catalog.
   - The resulting story is a clean contrast: *unknown → open, known-dangerous → closed.*

3. **Golden case regression suite** (`tests/golden/*.yaml` + parametrized runner)
   - Fixture shape: `name, dataset_urn, tags, quality_state, dlp_state,
     expected_verdict, expected_reason_code, origin`, where
     `origin ∈ {real_incident, synthetic}`.
   - Every verdict a human judges wrong becomes a permanent fixture with
     `origin: real_incident` — failures convert into reusable evaluation.
   - **Coverage gate**: every `reason_code` present in the policy must have
     ≥ 1 golden case; every verdict type ≥ 2. Adding a policy rule without a
     test fails the build.

4. **Structured verdict payload + evidence bundle**
   - Replace the bare verdict with
     `{verdict, reason_code, policy_version, evidence{urn, tags_consulted,
     quality_state, checked_at}, remediation{...}}`.
   - Self-contained: the payload alone explains the decision without a DataHub
     round-trip, which is what makes the audit trail defensible.

5. **Lineage-backed remediation (the demo moment)**
   - On `reason_code: deprecated_dataset`, walk existing lineage for a
     successor and return it in `remediation.suggested_dataset` with a
     schema-match flag, so the agent can retry within the same run.
   - Connects two features already built (guardrail + lineage); a BLOCK becomes
     a redirect instead of a wall.

6. **Risk-tiered deploy gating** (CI, path-filtered)
   | Change touches | Required gate |
   |---|---|
   | docs only | static checks |
   | `policies/*.yaml` | golden suite + coverage gate |
   | plugin / decision code | golden suite + integration tests |
   | write-back / audit path | above + structural check |
   - **Structural check blocks unconditionally**, regardless of pass rate:
     a verdict emitted without an audit write-back, or a policy rule with no
     golden case, fails the merge.

7. **Documentation & submission update**
   - Roles table (Human owns SSOT/policy/merge · Agent interprets & drafts ·
     Code enforces deterministically & audits) in README + Devpost.
   - Rewrite "55-check test suite" as "N unit tests + M golden governance cases
     with a coverage gate" — accurate once §3 lands.
   - Record our **own** measured numbers (see Success criteria).

## Non-goals

Deferred to "What's Next", not this cycle: nightly DataHub drift → auto-PR loop;
column-level guardrails / field masking; execution guards (query cost dry-run,
scan-size and time-range caps, idempotency tokens); real
`upsertStructuredProperties`; guardrail verdicts as Splunk HEC alert events.

## Success criteria

- `policies/governance.yaml` is the only source of rules; decision code contains
  no rule literals, and the loader is covered by tests.
- Golden suite green with coverage gate enforced; demonstrated by adding a
  throwaway policy rule and watching the build fail for a missing case.
- HIPAA-tagged + unscanned dataset returns **BLOCK**; DataHub-unreachable path
  still returns **ALLOW** with `metadata_unavailable`.
- At least one demo scenario where a deprecated-dataset BLOCK carries a
  `suggested_dataset` from lineage.
- Existing 55 checks still pass — zero regression, DataHub layer stays env-gated
  so the base platform runs identically without it.
- Measured and recorded for the submission (our numbers, not borrowed):
  guardrail decision latency p50/p95, context cache hit rate, share of runs
  whose verdict ≠ ALLOW, golden case count, and policy coverage
  (datasets with an applicable rule / total datasets in the demo graph).

## Sequencing (if time-boxed before a submission deadline)

1 → 3 → 7 first: externalizing the policy and standing up the golden suite makes
the strongest claim and is mostly mechanical. Then 5 for demo impact, then 2 and
4. Item 6 is cheap to describe in the write-up even if CI wiring lands later —
but only claim what actually runs.
