# Implementation Plan: A finished authoring run leaves no proposal behind

**Branch**: `spec/052-authoring-payload-retention` | **Date**: 2026-08-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/052-authoring-payload-retention/spec.md`

## Summary

041's FR-033 closed one of the two places a customer's authored content rests in the control
plane. This closes the other. At the run's terminal state — after `_publish_the_proposal`
returns, in the proposer task only — the stored payload's authored file bodies and
model-authored rationale are cleared, and the path-and-digest manifest that already exists in
`provenance` is kept, so a reviewer can still prove a merged pull request is the proposal the
run made.

Research made three things cheaper and one thing bigger. The trigger point already exists
beside the intents scrub ([R1](research.md)); the manifest FR-009 wants is already written by
`proposal_payload` ([R2](research.md)); and no provider method is needed, because `save`
already upserts by `blob_id` ([R4](research.md)). Against that, **six existing checkpoints hold
~81 KB of authored content** and a forward-only scrub would leave every one of them
([R7](research.md)) — the acceptance signal is a sweep of the live store, so this feature
backfills or it has not closed #219.

Two findings the spec did not anticipate are carried below: a requirement whose case does not
exist, and the backfill the spec has no requirement for.

## Technical Context

**Language/Version**: Python 3.13, fully typed. No TypeScript — nothing in the portal reads the
proposal payload ([R8](research.md)).

**Primary Dependencies**: none added.

**Storage**: the existing checkpoint store, through the existing `DurabilityProvider.save`.
**No schema change and no new provider method** — `save` upserts by `blob_id`, which every run
already exercises.

**Testing**: `tests/unit/` (the pure scrub function and its field selection),
`tests/conformance/durability/` (the stored-JSON round trip, the refusal path's absent subject,
the backfill), and the existing `test_dispatched_no_secret_sweep` row from #219 as the
acceptance signal.

**Target Platform**: unchanged — enclave allocation, both durability providers.

**Project Type**: existing single project. One pure function in core, one call site in a
surface, one operator-invocable backfill.

**Performance Goals**: none binding. One additional `save` per authoring run, against a run
that has just made a network call to a forge.

**Constraints**: the scrub must not run in the analyzer task (FR-002, US3 — the analyzer's
checkpoint is the handoff the proposer reads); it must run after `_publish_the_proposal`
returns, because that function writes the terminal payload itself (FR-010); `provenance` and
`files[].path` must survive (FR-009); a scrub that cannot complete must stop with the reason
recorded rather than report a clean run (FR-005).

**Scale/Scope**: 6 existing checkpoints to backfill; ~81 KB. Every authoring run thereafter.

## Constitution Check

*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md)
v1.6.0 (Last Amended 2026-08-05) — checked against that version.*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | Pass | A pure function and a call site. No new module, no framework, nothing adopted |
| II — Total Interception; One Governed Tool Layer | N/A | No tool, transport, or egress class is touched. The scrub is a store write on a path the run already owns |
| III — Fail-Closed, In-Process Enforcement | Pass | FR-005: a scrub that cannot complete stops with the reason recorded. The failure this cannot detect afterwards is reporting a clean run over content still present, so the row asserts the store, not the return value |
| IV — Zero Standing Credentials; Authority Per Task | Pass | The scrub runs in the proposer task under the authority it already holds, on a blob it already wrote. No new credential, no widened scope |
| V — Sealed Core, Versioned Seams | Pass | **And deliberately so.** [R4](research.md) rejects a second provider method: `save` already upserts by `blob_id`, so the durability seam is used rather than widened. The one sealed-core file touched is `core/authoring/retention.py`, additively |
| VI — Lean by Default | Pass | No operated component, no dependency, no scheduled job. FR-011's sweeper is explicitly *not* built here |
| VII — Anti-Fragmentation | Pass | The scrub lands beside the intents scrub rather than at a second place a run can be declared finished |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | N/A | No pack, prompt, model, or policy content changes |
| IX — Evidence Over Claims | Pass | **The principle this feature is balanced on.** US2 is P1 precisely because a scrub satisfying US1 alone would delete the content *and* the ability to say what happened. [R2](research.md) is what makes both hold at once: the manifest already exists, so nothing is traded |
| X — The Decision Record Governs | Pass | ADR-0024 (the seam is used, not widened), ADR-0026 (the open/closed reasoning redone for a payload rather than inherited), ADR-0018 (what survives must compile a report), ADR-0038 (the pull request is the durable artifact, which is what makes clearing the platform's copy possible), ADR-0047. No Accepted ADR contradicted; none needed |

**Gate result**: **PASS — proceed to Phase 0.**

### Carried findings that need a spec sentence

Both must reach `/speckit-analyze` and from there `/speckit-clarify`. Neither blocks this plan.

1. **FR-007's case does not exist** ([R6](research.md)). A run refused at Judge returns before
   Propose and never composes a proposal, so there is nothing in its payload to scrub. A row
   asserting FR-007 as written would pass without exercising anything. The requirement should
   be restated as what is actually true and checkable: a refused run's payload contains no
   authored content in the first place.
2. **The backfill has no requirement** ([R7](research.md)). Six checkpoints already hold
   authored bodies, all terminal. SC-001 says 100% and the acceptance row sweeps the whole
   table, so a forward-only scrub leaves #219 red. The plan builds the backfill; the spec does
   not ask for it.

## Project Structure

### Documentation (this feature)

```text
specs/052-authoring-payload-retention/
├── plan.md              # This file
├── research.md          # Phase 0 — R1–R8
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── payload-retention.md            # what is cleared, what survives, when
│   └── conformance-payload-retention.md # gate rows, hermetic and named-runner
├── checklists/
│   └── requirements.md  # existing, from /speckit-specify
└── tasks.md             # Phase 2 — /speckit-tasks, NOT created here
```

### Source Code (repository root)

```text
src/core/authoring/
└── retention.py      # scrub_proposal_payload() — pure; decides WHAT is content.
                      # Beside CONTENT_BEARING_TOOLS, which is the same knowledge

src/surfaces/dispatch/
└── entrypoint.py     # the call, in the PROPOSER branch only, after publish returns 0

scripts/
└── backfill-proposal-payloads.py   # one-time, idempotent, over terminal checkpoints

tests/
├── unit/                        # field selection, idempotence, the manifest survives
└── conformance/durability/      # stored-JSON round trip; refusal path; backfill;
                                 # and #219's existing sweep row as the acceptance signal
```

**Structure Decision**: existing layout, no new module. The split is deliberate and is the
plan's main structural claim: **what counts as content is authoring knowledge** and lives in
`retention.py` beside `CONTENT_BEARING_TOOLS`; **how a payload is stored** is the provider's,
and is already provided. Putting field selection into SQL would put authoring knowledge in the
durability provider, which is the layering error `AGENTS.md` names.

## Implementation order

| # | Slice | Delivers | Why here |
| --- | --- | --- | --- |
| 1 | `scrub_proposal_payload`, pure | FR-008, FR-009 | Everything else calls it. Testable with no store |
| 2 | The call site, proposer branch only | FR-001, FR-002, FR-010, US1, US3 | Needs 1. The gating is the part that can break durability |
| 3 | Fail-closed and idempotence | FR-005, FR-006 | Needs 2 |
| 4 | Attestation rows | FR-003, FR-004, US2 | Needs 2; asserts what survives rather than what went |
| 5 | The backfill | R7, SC-001 | Needs 1. Last, because it is the same function applied to history |
| 6 | The acceptance sweep | SC-006, FR-013 | #219's row goes green only after 5 |

## Post-Design Constitution Re-check

*Re-run against v1.6.0 after Phase 1. No verdict moved; two are strengthened by what the design
settled, and one weakened claim is corrected.*

| Principle | Verdict | What Phase 1 changed |
| --- | --- | --- |
| I — Build Glue Only | Pass | Final surface: one pure function, one call site, one script. No module added |
| II — Total Interception | N/A | Unchanged |
| III — Fail-Closed | Pass | **Sharpened.** Contract §3 asserts the refusal *against the stored row*, not the return value — a scrub that reported a count while leaving the row intact is the exact failure FR-005 names, and a return-value assertion could not see it |
| IV — Zero Standing Credentials | Pass | Unchanged. The scrub writes a blob the task already wrote, under authority it already holds |
| V — Sealed Core, Versioned Seams | Pass | **Strengthened by subtraction.** [R4](research.md) rejected a second provider method; the durability seam is used rather than widened, and the one sealed-core file touched is `retention.py`, additively. Contract §6 lists what is deliberately unchanged so a later reader can tell restraint from oversight |
| VI — Lean by Default | Pass | A one-time script, not a sweeper. FR-011's case has zero instances today ([R7](research.md)), so a scheduled job would be operated machinery with nothing to sweep |
| VII — Anti-Fragmentation | Pass | One scrub site, beside the existing one. No second place a run can be declared finished |
| VIII — Eval-Gated Promotion | N/A | Unchanged |
| IX — Evidence Over Claims | Pass | **The principle the design turns on.** [R2](research.md) found the path-and-digest manifest already in `provenance`, so US1 and US2 do not trade. Row A3 asserts it **by name** rather than inferring it from the cleared list, because a change that took it would satisfy retention, destroy attestation, and look tidier while doing it |
| X — The Decision Record Governs | Pass | ADR-0024 honoured by *not* widening the seam; ADR-0026's open/closed reasoning redone for a payload rather than inherited ([R1](research.md), [R5](research.md)); ADR-0018 satisfied by A12–A14; ADR-0038 is what makes clearing the platform's copy defensible at all |

**Gate result**: **PASS — design stands.**

### Corrections the design forced

| Finding | Correction |
| --- | --- |
| A second provider method looked symmetric with 041 | 041's `scrub_closed_arguments` exists because clearing intents is a bulk `UPDATE` across a join. This is one blob the caller holds, and `save` already upserts by `blob_id`. Symmetry would have widened a sealed-core seam to do what it already does, and moved authoring knowledge into the durability provider |
| The Postgres row's justification does not transfer | 041's leg is justified by "in-memory clears a field for free". With no new SQL that argument is empty, so E1 asserts the **stored text** instead — which catches saving the pre-scrub object, the thing that can actually go wrong |
| FR-007 asks for something unobservable | A refused run never composes a proposal ([R6](research.md)), so the row asserts the *absence* — and goes red if the refusal path ever starts carrying one |

## Complexity Tracking

No Constitution Check violation requires justification. One judgement is recorded because it
went the less obvious way:

| Item | Why the simpler-looking option was rejected |
| --- | --- |
| No `scrub_checkpoint_payload` on the durability provider | Symmetry with 041's `scrub_closed_arguments` is superficially attractive. That method exists because clearing intents is a bulk `UPDATE` across a join — real SQL work. This is one blob the caller already holds, and `save` already upserts by `blob_id`. Adding a method would widen a sealed-core seam (Principle V) to do what the seam does, and would move authoring knowledge into the durability provider |
| A one-time script rather than a scheduled sweeper | FR-011's never-terminal case has **zero instances today** ([R7](research.md)), so a sweeper would be operated machinery with nothing to sweep. The six existing rows are a fixed, finite set and a script clears them once |
