# Conformance: Capability Packs and Eval Gates

**Feature**: `specs/013-capability-packs` | **Date**: 2026-07-29 | **Status**: Planned

Four gates in force, one recorded as owed, and a per-cell record of which scorer qualified
what. These rows are blocking from the moment this feature lands (ADR-0047).

---

## The eval gates

| Suite | Asserts | Blocking |
| --- | --- | --- |
| `must_deny` | Safety refusals the agent must make | Yes |
| `must_decline` | Requests outside declared scope declined with a pointer elsewhere (ADR-0034/0036) | Yes |
| `citation_accuracy` | Every substantive claim carries a citation that resolves; absent grounding produces a decline rather than confabulation | Yes |
| `estate_state` | Answers about the estate match recorded fixtures | Yes |
| `report_fidelity` | — | **OWED (ADR-0018)** |

**Why report fidelity is owed rather than green.** `RunReport` does not exist in `src/`.
A suite over it would assert something about a thing that is not there, and ADR-0047's rule
is explicit: absent, or an explicit skip citing its deferring record — never a passing stub,
and never a weaker property asserted under its name. Recorded here so the eval-gate row
reads as four-of-five rather than as complete.

## Structural rows

| Row | Asserts |
| --- | --- |
| The core is product-blind | No module under `src/core` contains any product name. Adding the second pack changed no core file — **shown by the diff**, not argued (SC-002, SC-012) |
| No bypass path | Every pack tool is a `ToolRegistry` registration; no pack-specific invocation path exists (FR-003) |
| A pack cannot widen a ceiling | A pack declaring a tool outside its definition's ceiling refuses `pack_exceeds_ceiling`; zero paths grant from a manifest (FR-005) |
| Packs are isolated | Two packs loaded; neither reachable from a definition that does not name it. An ambiguous unqualified tool name refuses rather than resolving by load order |
| No auto-tracking | Asserted as an absence: no alias, no "latest", no configuration that would produce one (FR-011) |
| No unqualified model is reachable | Including fallback, including when the pinned cell is withdrawn (FR-010, SC-004) |
| A verdict is not an approval | `MODEL_GATE` and any human approval are distinguishable in the trail (FR-015) |
| Digests are verified at load | A skill whose bytes changed without its pin changing refuses `digest_mismatch` |
| Promotion needs all three | Provenance, injection lens, and a passing eval — any one absent blocks (FR-017, SC-006) |

## The per-cell qualification record (SC-013)

**Every qualified cell records which scorer qualified it.** This table is the record, and a
cell absent from it is not qualified.

| Pack | Model | Role | Scorer | Date | Judge |
| --- | --- | --- | --- | --- | --- |
| _(populated at implementation)_ | | | | | |

A `fixture` cell is qualified against a recording. That is a real limit, per cell, and the
column exists so it cannot be read as more than it is.

## Break fixtures worth naming

- **A pack that grants.** Declare a tool outside the definition's ceiling and let the load
  succeed. The no-widening row must fail. This is the most plausible defect in the feature:
  it reads as the pack system working.
- **A cell qualified by the cell it qualifies.** Point a judge at itself. The chain must
  refuse rather than closing the loop silently.
- **A withdrawn cell that keeps running.** Qualify, pin, withdraw, run. The run-start
  validation must refuse `cell_withdrawn`; if only registration validated, this passes.
- **A skill bumped without review.** Change content, update the digest, skip the lens.
  Promotion must block.
- **An alias that resolves to latest.** Add one. The no-auto-tracking row must fail.
- **A model verdict filed as an approval.** Record a `judge` verdict under an approval-shaped
  event. The distinction row must fail.

## Who runs these

| Where the change comes from | What covers these rows |
| --- | --- |
| Same-repo branch or pull request | The fast lane (fixtures) and the enclave lane. Required checks |
| Fork pull request | The agent harness in the IDE, per `AGENTS.md` |
| **The live-model lane** | **Dan, before merge** — see below |

**Named runner** (constitution v1.1.0): the live-model lane needs a provider credential and
costs money per run, so it cannot sit in CI. Dan runs it and records the per-cell outcome in
the table above. Merging without that record is a gate regression.

*This is a genuine named-runner case, unlike 012's accessibility checklist — which was
deferral disguised as rigour, because a browser could do the work and was already installed.
Here the obstacle is a paid credential and non-determinism inside a merge gate, not missing
tooling. The blocking lane still runs every gate.*

## Sealed-core review

Two additive changes: `risk_class` on `ToolRegistration`, and `MODEL_GATE` / `MATRIX_FALLBACK`
on `AuditEventType`. Approved spec: this feature's. Security-maintainer review: Dan.
