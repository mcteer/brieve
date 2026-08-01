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

**Target Platform**: The enclave, for the surface rows. The compiler itself needs no
infrastructure, which is the point of the seam in research F6.

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
| IV — Zero Standing Credentials; Authority Per Task | **FAIL — see below** | **Read-back at report time has no authority to run under.** |
| V — Sealed Core, Versioned Seams | **Pass, conditionally** | Nothing sealed changes *as specified*. One candidate resolution to the Principle IV failure would change the `Observer` protocol, which is core — that would make this a sealed-core change needing security-maintainer review, and it is called out below rather than discovered later. |
| VI — Lean by Default | **Pass** | No new dependency, no new operated component, no new store. |
| VII — Anti-Fragmentation | **Pass** | The compiler consumes `read_evidence_for` rather than reaching `EvidenceQuery.search`, so there is no second answer to "who may see this" (research F1). |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | **Pass** | Turns the fifth gate on. Promotes nothing. |
| IX — Evidence Over Claims | **Pass** | The whole feature. FR-010 additionally requires a report to state whether its own basis verified. |
| X — The Decision Record Governs | **Pass** | ADR-0018 implemented, ADR-0035/0032/0055/0033/0034 consumed. None amended. |

**Gate result**: **FAIL — planning stops at Principle IV.**

### The failure, measured

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
| **A** | **Drop read-back.** US3 leaves this feature; every effect claim carries `unverified: record only`. | Loses the ADR-0018 property that arguably matters most — the "applied successfully to three workspaces" failure the ADR opens with stays possible. | Clean. Nothing re-reads anything. |
| **B** | **Read-back under manufactured requester authority.** `manufacture_authority` for the requester, threaded into `observe()`. | Changes the `Observer` protocol — **sealed core** (`core.observation`), plus the pinned call-shape test and both shipped observers. | Compliant, but converts this into a sealed-core feature with the review that entails. |
| **C** | **Read-back at run end, recorded as evidence.** The allocation — which already holds the right attested identity and already re-observes — records an `Observation` for each effect before it exits. The report compiles that record like any other. | The observation is a fact about run-end, not report-time, so "the world changed since" stops being detectable. Adds work to the run loop. | Clean, and arguably the most faithful: ADR-0018 says read-back happens *before asserting completion*, and run-end is when the run asserts it. |

**My reading is C**, because it puts the read-back where the authority already exists rather than
manufacturing a new one, and because it needs no sealed-core change. It does partly walk back the
on-demand rationale — a report would no longer detect drift after the run ended — which is a real
loss and is exactly why this is not mine to decide.

**This is a spec-level question, not an implementation detail.** Whichever answer holds, US3 and
FR-006/FR-016 change, and per the pipeline rule that invalidates the clarification below them:
`/speckit-clarify` needs to record it, and this plan needs re-running against the result.

## Project Structure

### Documentation (this feature)

```text
specs/021-grounded-run-reports/
├── plan.md              # This file — HALTED at the Constitution Check
├── research.md          # Phase 0 — seven findings, one unknown carried
├── spec.md
├── checklists/
│   └── requirements.md
└── tasks.md             # NOT created — blocked on the gate
```

Phase 1 artifacts (`data-model.md`, `contracts/`, `quickstart.md`) are **not** written. The gate
failed, and the plan template is explicit that a failing gate stops planning rather than
proceeding into design that a resolution would invalidate.

### Source Code (repository root)

Recorded from research F6 so the shape is not re-derived, and marked provisional because
resolution B or C would move part of it:

```text
src/core/reports/                # NEW — typed RunReport, Claim, the compiler.
│                                # Pure: records in, report out. No surface import.
src/surfaces/api/reports.py      # NEW — the governed read + the route
src/surfaces/mcp/operations.py   # +1 operation map entry
src/surfaces/mcp/transport.py    # +1 dispatch entry
src/core/evals/suites.py         # report_fidelity moves OWED → SUITES
packs/*/evals/report_fidelity.toml  # NEW — recorded runs, labelled material events
specs/008-northbound-api/contracts/operations.snapshot.json  # regenerated
```

**Structure Decision**: the compiler is core and takes already-read entries; the governed read
stays where governed reads live. Core importing `surfaces` would be the layering inversion 020
found one package over.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| **Principle IV, unresolved** | Read-back at report time has no bounded authority available to it. | Not yet justified — three candidate resolutions are recorded above and the choice belongs to the maintainer. **This row must be empty or the violation withdrawn before implementation begins.** |
| **A fifth eval-case shape** (if the feature proceeds) | Report fidelity scores a compiled report against labelled material events, measured by precision and recall. The existing `EvalCase` is `(prompt, expected, recorded)` scoring a model's answer, and `EXPECTED_OUTCOMES` has no entry for it (research F3). | **Forcing it into `expected: str`**: rejected — it reduces fidelity to a boolean, losing the precision and recall FR-013a requires, or smuggles a structure into a string. **A gate outside `suites.py`**: rejected — the constitution names five suites in one place, and moving one out leaves `SUITES` a list of four forever. |
