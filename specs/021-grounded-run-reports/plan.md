# Implementation Plan: A report compiles from records, or it says it could not

**Branch**: `spec/021-grounded-run-reports` | **Date**: 2026-08-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/021-grounded-run-reports/spec.md`

## Summary

Compile the run records into the artifact a human actually reads, with every claim traced to
evidence and every gap stated rather than smoothed. `RunReport` has been Accepted since ADR-0018
and built by nothing; the fifth eval suite carries it in an `OWED` dictionary. This builds the
object, makes it requestable, and turns the last owed Quality Gate row on.

**The compiler reads nothing itself.** It receives entries the governed evidence read already
returned, which is what makes "a report grants no new access" structural rather than promised.

## Technical Context

**Language/Version**: Python 3.12.

**Primary Dependencies**: None new. The evidence read (`read_evidence_for`), the `Observer`
protocol, and the eval suite loader all exist.

**Storage**: **None.** A report is compiled on demand and never persisted (FR-014a) — no store,
no identity, no retention policy.

**Testing**: `pytest`. The fidelity suite is hermetic by construction (recorded runs, labelled
material events); the surface rows join the existing API and MCP conformance directories, and
the parity snapshot at `specs/008-northbound-api/contracts/operations.snapshot.json` is
regenerated.

**Target Platform**: The enclave, for the surface rows and for the run that observes. The
compiler itself needs no infrastructure — it takes records and returns a report — which is the
point of the seam in research F6 **as amended after the Constitution Check** (F6's original table
had the compiler calling `observe()`, which is what Principle IV rejected).

**Project Type**: A new core package, one API route, one MCP operation, and a fifth eval suite.

**Performance Goals**: None invented. But see **Constraints** — there is a correctness problem
hiding in a performance question.

**Constraints**: `EvidenceQueryRequest.limit` defaults to **1000**. A 400-step dispatched run
(the durability fixtures' size) writes roughly seven entries per step, so a report over one would
compile from a **truncated read** and state claims about a run it had only partly seen. That is
not a latency concern to defer; it is a report that is confidently wrong, and it must be handled
as a correctness requirement.

**Scale/Scope**: One typed object, one compiler, two transport registrations, one eval suite.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | Compiling records into a typed object is this codebase's own domain work, not a duplication of anything upstream ships. No model is asked anything (FR-001). |
| II — Total Interception; One Governed Tool Layer | **Pass** | A report issues no tool call. It becomes a northbound operation, so ADR-0033's parity obligation applies and FR-015b treats the row's growth as inherited work. |
| III — Fail-Closed, In-Process Enforcement | **Pass** | Unreconcilable claims are flagged, never softened (FR-005). The meta-audit write already fails the read rather than proceeding (`_record_access`). No observer yields `unverified`, never `confirmed` (FR-016a). |
| IV — Zero Standing Credentials; Authority Per Task | **Pass — after redesign** | Failed on first pass; see below. Read-back now happens in the allocation, under its own attested identity bounded by the run's ceiling (FR-006b). Nothing acts on a reader's behalf, so a report cannot exceed its reader. |
| V — Sealed Core, Versioned Seams | **Pass, WITH REVIEW OWED** | **The audit schema is touched.** One additive `AuditEventType` member carries the observation. Principle V names the audit schema sealed core and requires an approved spec plus security-maintainer review; the spec is approved, the review is owed before merge. Recorded in Complexity Tracking as a real obligation, exactly as 020 recorded its own. |
| VI — Lean by Default | **Pass** | No new dependency, no new operated component, no new store. |
| VII — Anti-Fragmentation | **Pass** | The compiler consumes `read_evidence_for` rather than reaching `EvidenceQuery.search`, so there is no second answer to "who may see this" (research F1). |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | **Pass** | Turns the fifth gate on. Promotes nothing. |
| IX — Evidence Over Claims | **Pass** | The whole feature. FR-010 additionally requires a report to state whether its own basis verified. |
| X — The Decision Record Governs | **Pass** | ADR-0018 implemented, ADR-0035/0032/0055/0033/0034 consumed. None amended. |

**Gate result**: **PASS — proceed to Phase 1**, with the Principle V review recorded as owed.

**Re-check after Phase 1 design**: **PASS**, unchanged. **Two** items remain in Complexity
Tracking — the sealed-core audit member, and the fifth eval-case shape — and neither grew during
design. (This sentence said "the only item" until analysis pass 3; a Constitution Check statement
that miscounts the table beneath it is the kind of thing a reviewer reads instead of the table.)

### The failure, measured — kept because the redesign is only legible beside it

FR-006 requires re-reading authoritative state before claiming an effect completed, and
clarification put that read-back **at report time** (compiled on demand) **wherever an observer
exists**. Measured against the tree, there is no authority for it to run under:

- `Observer.observe(*, idempotency_key)` takes **one argument and no credential**
  (`src/core/observation/types.py:39`). `tests/unit/test_observers_match_the_protocol.py` pins
  that call shape — it exists because 013 shipped an observer whose signature disagreed with its
  only caller, and every interrupted Vault write suspended its run forever as a result.
- `VaultWriteObserver.observe` therefore reads under **ambient** credentials — `_fabric()` at
  `src/surfaces/handlers.py:118`.
- In a resume that ambient identity is *the allocation's*, attested and bounded by the run's
  ceiling. **At report time there is no allocation.** The API surface holds its own workload
  identity (the `api` Vault role), so a read-back would run under the *surface's* authority.

That is amplification: an auditor requesting a report would obtain an observation of product
state that they may hold no authority to make, produced by a process whose identity is not
theirs. Principle IV is explicit — effective authority is bounded by the requesting human, and
"an agent never exceeds its human". A report must not exceed its reader.

It is also not a corner case. It is the **normal** path for US3 as clarified, and it follows
directly from two answers that were each individually right: compile on demand, and read back
wherever an observer exists.

### Three resolutions, none of which I should pick alone

| | Resolution | Cost | Constitution |
| --- | --- | --- | --- |
| **A** | **Drop read-back.** US3 leaves this feature; every effect claim carries `unverified_not_observed`. | Loses the ADR-0018 property that arguably matters most — the "applied successfully to three workspaces" failure the ADR opens with stays possible. | Clean. Nothing re-reads anything. |
| **B** | **Read-back under manufactured requester authority.** `manufacture_authority` for the requester, threaded into `observe()`. | Changes the `Observer` protocol — **sealed core** (`core.observation`), plus the pinned call-shape test and both shipped observers. | Compliant, but converts this into a sealed-core feature with the review that entails. |
| **C** | **Read-back at run end, recorded as evidence.** The allocation — which already holds the right attested identity and already re-observes — records an `Observation` for each effect before it exits. The report compiles that record like any other. | The observation is a fact about run-end, not report-time, so "the world changed since" stops being detectable. Adds work to the run loop. | Clean, and arguably the most faithful: ADR-0018 says read-back happens *before asserting completion*, and run-end is when the run asserts it. |

### Resolved: **C**, and one part of the recommendation was wrong

The maintainer chose C. Read-back moves into the allocation, which already holds an attested
identity bounded by the run's ceiling, and the observation is recorded as evidence for the report
to compile like anything else. The compiler stays pure — it still reads nothing itself, which is
what keeps FR-008b structural.

**Correction to the recommendation above**: it said C "needs no sealed-core change". That was
wrong. C does not touch the `Observer` **protocol** — which is what B would have done, and which
is the larger change — but the observation has to be recorded somewhere, and the honest home is
the hash-chained trail. That is one additive `AuditEventType` member, which is a Principle V
change requiring security-maintainer review. Smaller than B, not free, and the plan now says so in
the gate table rather than carrying a claim that would have been discovered at implementation.

**What C costs, carried forward rather than left in the clarification log**: a report no longer
detects drift after the run ended. An observation is a fact about run-end — which is when
ADR-0018 says the claim is made, "before asserting that something completed" — so a product
changed a week later reads identically to one that never changed. Accepted deliberately.

**What C buys beyond compliance**: two reports of the same run now agree on *every* claim, not
merely on the record-derived ones, because nothing is re-derived at request time. That is a
stronger guarantee than the on-demand clarification originally anticipated.

## Project Structure

### Documentation (this feature)

```text
specs/021-grounded-run-reports/
├── plan.md              # This file
├── research.md          # Phase 0 — seven findings, one unknown carried
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── report.md        # What a report contains, and what each claim's status means
│   └── conformance.md   # The rows, who runs them, what they refuse to assert
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
src/core/audit/schema.py         # +1 AuditEventType member. SEALED CORE — see Principle V
src/core/reports/                # NEW — the typed object and the compiler
│   ├── __init__.py
│   ├── report.py                # RunReport, Claim, ClaimStatus
│   └── compile.py               # records in, report out. Reads nothing itself
src/core/observation/            # UNCHANGED — the protocol is not touched (that was option B)
src/surfaces/dispatch/entrypoint.py  # observes each effect before a terminal state, under the
│                                    # allocation's own attested identity (FR-006b)
src/surfaces/api/reports.py      # NEW — the governed read + the route
src/surfaces/mcp/operations.py   # +1 operation map entry
src/surfaces/mcp/transport.py    # +1 dispatch entry
src/core/evals/suites.py         # report_fidelity moves OWED → SUITES; a fifth case shape
packs/*/evals/report_fidelity.toml  # NEW — recorded runs, labelled material events
specs/008-northbound-api/contracts/operations.snapshot.json  # regenerated — parity grows
infra/bin/reports-conformance    # NEW — the lane for the rows that need a dispatched run
tests/conformance/reports/       # NEW — rows against a compiled report; hermetic AND enclave,
│                                # so the lane must select the markers (see tasks T029a)
```

**Structure Decision**: the compiler is core and takes already-read entries; the governed read
stays where governed reads live; the **observation is made by the allocation**, which is the only
process holding an identity bounded by the run's ceiling.

That last point is the whole of the Principle IV redesign, and it is a structural property rather
than a rule to follow: `compile_report` receives entries and never queries, so it cannot widen
scope, and it holds no credential, so it cannot observe. **A future change that gave the compiler
a way to read a product would have to add both** — which is a visible thing to review rather than
a silent regression.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| **A sealed-core change: one `AuditEventType` member** | The observation must be recorded somewhere, and the trail is the only store that is hash-chained, tenant-scoped, readable through the governed evidence path the report already uses, and append-only. Recording it anywhere else would give the report a second source to reconcile. | **On the checkpoint payload**: rejected — checkpoints hold resume state, and `run_result_for` already argues that returning their contents makes their shape a compatibility surface. **A new durability record type**: rejected — it would be a second store for evidence, reachable outside the audited read path, which is FR-007's whole objection. **The obligation stands regardless**: Principle V requires security-maintainer review of an audit-schema change, and "additive" is the word that precedes most sealed-core regressions. |
| **A fifth eval-case shape** | Report fidelity scores a compiled report against labelled material events, measured by precision and recall. The existing `EvalCase` is `(prompt, expected, recorded)` scoring a model's answer, and `EXPECTED_OUTCOMES` has no entry for it (research F3). | **Forcing it into `expected: str`**: rejected — it reduces fidelity to a boolean, losing the precision and recall FR-013a requires, or smuggles a structure into a string. **A gate outside `suites.py`**: rejected — the constitution names five suites in one place, and moving one out leaves `SUITES` a list of four forever. |
