# Implementation Plan: A deployment lane — every deployed process is proven to run

**Branch**: `spec/017-deployment-lane` | **Date**: 2026-07-31 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/017-deployment-lane/spec.md`

## Summary

Every existing gate asserts about a process the test itself constructs. None asserts about
the process a deployment runs, and `build()` — the assembly — is the one code path with no
coverage by construction. On 2026-07-31 the northbound API was found never to have served a
request in a deployed enclave.

**Research shrank this feature by half.** Two of the four deployed processes are already
covered: 014's durability rows dispatch real `agent-run` allocations and assert completion,
and 015's shipping row requires the running mcp service to have booted and obtained a
credential. The API and the portal are covered by nothing, because no lane invokes
`portal-up`. See [research.md](research.md) R1 and R2.

The approach is therefore composition, not construction:

1. **Sequence, don't parallelise.** Extend the existing enclave lane: after
   `make conformance` completes and the batch job releases its reservation, stand the two
   uncovered surfaces up and assert against them. FR-007 is satisfied structurally — nothing
   competes — rather than by tuning resource numbers that have already failed once (R4).
2. **Assert a refusal, not a health check.** The API's assembly migrates three stores under
   its attested identity *before* uvicorn binds, so answering at all entails reaching Vault
   and Postgres. An unauthenticated request returning the surface's own reason code is
   unproducible by a process that read nothing (R3).
3. **Reach surfaces through the scheduler.** `nomad alloc exec`, not the shell — host
   networking means the shell can reach them on a Linux runner and cannot on macOS (R5).
4. **Enumerate from the deployment, failing closed on discovery.** The gate reads *every*
   job definition and requires each to be a declared subject or an explicitly excluded one;
   a definition that is neither fails the gate (R6, FR-005a). Analysis pass 1 corrected this
   — the first design read only *marked* definitions, so a process nobody enrolled was
   invisible, which is this feature's own subject matter one level up.

## Technical Context

**Language/Version**: Python 3.12 (the repository's pinned interpreter)

**Primary Dependencies**: pytest with the existing `enclave` / `host_enclave` markers; the
Nomad CLI, already required by `make dev-up`. **No new dependency is introduced** — a gate
that added one would need a named trigger under Principle VI.

**Storage**: N/A. This feature writes nothing and reads no store of its own.

**Testing**: pytest, in `tests/conformance/deployment/` — a new directory, which must be
named by a lane in the same change that creates it (010 lost a feature's rows to a directory
no lane enumerated; the `make conformance` recipe records that at length).

**Target Platform**: The local enclave on Docker Desktop (macOS) and the Linux CI runner.
Both must reach the same verdict — FR-008, and Principle VII's identical-suite requirement.

**Project Type**: Conformance gate over infrastructure. No `src/` change is expected;
if one proves necessary, that is a finding worth reporting rather than a silent edit.

**Performance Goals**: Per-process waits only. There is deliberately no whole-gate budget —
clarified 2026-07-31, because a single budget reports whichever process was slow as the gate
overrunning, which is the misattribution FR-004 exists to prevent.

**Constraints**: The lane must not make the merge-blocking rows unplaceable (FR-007), a
documented past failure. No retries (FR-014). The lane must add no second enclave bring-up.

**Scale/Scope**: Eight job definitions, every one of which needs a verdict — four declared
subjects (two already covered elsewhere, two to add), three explicit exclusions, and
`harness-probe`, which analysis pass 1 found unaddressed. One new conformance directory, one
addition to the CI lane.

## Constitution Check

*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md) (v1.3.0).*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **N/A** | No product knowledge, no framework capability. A gate over deployment. |
| II — Total Interception; One Governed Tool Layer | **N/A** | No tool call is made or intercepted. |
| III — Fail-Closed, In-Process Enforcement | **Pass** | FR-006 makes an absent or restarting process a failure, never a skip. The gate has no permissive branch. |
| IV — Zero Standing Credentials; Authority Per Task | **Pass** | Adds no credential. The assertions run through the scheduler and require no token; the surfaces authenticate as they already do. The one place this could go wrong — passing an admin token in to make an assertion easier — is explicitly rejected in the contract. |
| V — Sealed Core, Versioned Seams | **Pass** | No core change expected. The gate observes surfaces from outside. |
| VI — Lean by Default | **Pass** | No new operated component and no new dependency. Sequencing inside the existing lane rather than adding a third is the direct application of this principle (R4). |
| VII — Anti-Fragmentation | **Pass, and load-bearing** | *"two ways to run the gate is two gates, and the one nobody runs locally is the one that rots."* R5's choice of `nomad alloc exec` exists precisely so the assertion is identical on both substrates; a host-shell curl would have made the suite substrate-dependent, which this principle permits only for the substrate itself. |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | **N/A** | No pack, prompt, model or policy promotes here. |
| IX — Evidence Over Claims | **Pass, and this is the feature** | The gate exists because "all gates pass" was reconcilable with a surface that had never started. SC-007 requires recording which known instances the gate would *not* have caught, so the claim is bounded by evidence rather than asserted. |
| X — The Decision Record Governs | **Pass** | Closes ROADMAP gap 0d. Touches ADR-0047 (a gate must not assert a weaker thing than its guarantee), ADR-0048, ADR-0033, ADR-0025. **No ADR is superseded or amended**, and none is needed: this builds a gate the constitution's Quality Gates already imply rather than deciding anything new. |

**Blocking-row ownership** (constitution v1.1.0, Quality Gates): this feature adds
merge-blocking rows, and **every one is executed by an automated check** — the enclave lane,
extended. **No named human runner is owed.** The conformance contract must record that
explicitly, because "no runner named" and "no runner needed" look identical in a table.

**Gate result**: **PASS — proceed to Phase 0**

*Re-checked after Phase 1 design: unchanged. The design adds no credential, no dependency,
no operated component, and no core module; the one principle it leans on hardest (VII) is
satisfied by R5 rather than compromised by it.*

## Project Structure

### Documentation (this feature)

```text
specs/017-deployment-lane/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── conformance.md   # What the rows assert, and what they do not
├── checklists/
│   └── requirements.md  # From /speckit-specify
└── tasks.md             # /speckit-tasks — NOT created here
```

### Source Code (repository root)

```text
infra/
├── jobs/
│   ├── api.nomad.hcl            # + meta: declares itself a deployed surface
│   ├── portal.nomad.hcl         # + meta
│   ├── mcp.nomad.hcl            # + meta (already covered; declares itself anyway)
│   └── agent-run.nomad.hcl      # + meta (already covered; dispatched shape)
└── bin/
    └── deployment-conformance   # NEW — stands the uncovered surfaces up, then hands off

tests/
└── conformance/
    └── deployment/              # NEW directory — MUST be named by a lane in this change
        ├── __init__.py
        ├── conftest.py          # allocation lookup; exec-based reach; per-process waits
        ├── surfaces.py          # enumerates EVERY infra/jobs/*.hcl; declared u excluded
        │                        #   must equal what is on disk (FR-005a)
        ├── test_every_declared_process_is_asserted.py   # FR-005/FR-005a, US3
        ├── test_the_api_answers_as_itself.py            # FR-003/FR-009, US1/US2
        ├── test_the_portal_read_its_configuration.py    # FR-003, US1/US2
        ├── test_the_dispatched_process_is_covered.py    # FR-005 for the dispatched shape
        ├── test_no_retry_and_no_skip.py                 # FR-014, by source inspection
        ├── test_break_a_surface_assembly.py             # FR-012, the break fixture
        └── test_the_gate_is_deterministic.py            # SC-008, run twice, compare

Makefile                          # `conformance` gains the new directory
.github/workflows/enclave.yml     # one step after `make conformance`
```

**Structure Decision**: A new `tests/conformance/deployment/` package, named by the
`make conformance` recipe **in the same change that creates it**. That is not tidiness — the
recipe's own comments record that 010 lost a whole feature's rows to a directory no lane
enumerated, and that 014 nearly repeated it with a directory that *was* named by a lane which
deselected the rows. Both failures are the shape this feature exists to close, and repeating
one inside it would be its own indictment.

`infra/bin/deployment-conformance` mirrors `infra/bin/enclave-conformance`: a script the CI
lane and a developer both invoke, so there is one way to run the gate (Principle VII).

## Complexity Tracking

> No Constitution Check violations. Table omitted.

One risk is worth naming without being a violation. **FR-005 and FR-008 pull against each
other**, as the spec's checklist flagged: enumerating from `infra/jobs/` satisfies
coverage-by-construction and works identically on both substrates, since it reads files
rather than querying a scheduler. R6 resolves the tension in that direction.

**Analysis pass 1 changed the enumeration default, and the cost with it.** The gate now
reads *every* definition and requires each to be declared or explicitly excluded (FR-005a),
rather than reading only the marked ones. The old scheme was fail-open: a definition added
without a marker was invisible, and a coverage mechanism that cannot see a gap is this
feature's own subject matter one level up.

The cost is now paid when a job definition is added rather than never — adding one fails the
gate until someone declares or excludes it. That is deliberate friction on the exact action
that has been silently losing coverage, and the contract records it so the first person to
hit it can tell it from a defect in one reading.
