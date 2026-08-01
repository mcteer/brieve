# Implementation Plan: The trail records who looked, or the surface stops saying it does

**Branch**: `spec/022-audited-reads` | **Date**: 2026-08-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/022-audited-reads/spec.md`

## Summary

Seven operations touching runs and threads currently write nothing to the audit trail, while both
surfaces tell every client that every operation is recorded. Six are reads; the seventh, `stop_run`,
is a person terminating a run and was found by analysis pass 8 after this plan's first draft had
wrongly recorded it as covered. This feature makes all seven record, states the rule that decides which operations must, and derives the surfaces'
governance claim from that rule so it cannot overclaim again.

The approach is almost entirely **adoption rather than invention**. The evidence path already
records who read the audit plane: a stable per-tenant stream, a payload carrying query shape and
never rows, and a write whose failure fails the read. 022 applies that same shape to a second
stream for run and thread records, adds four additive audit event types, and moves the audit
disposition onto the operation catalogue as a required field so a future operation cannot ship
without deciding.

**One thing is genuinely new**: the governance sentence in the MCP surface's instructions becomes
*generated* from the catalogue's dispositions rather than hand-written. A check comparing a
hand-written claim to a second hand-written copy would have passed every day this gap existed.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: FastAPI (API surface), FastMCP (MCP surface), Pydantic v2, SQLAlchemy
(audit sink). **No new dependency.**

**Storage**: PostgreSQL — the existing `audit_entries` table and hash-chained streams. No schema
migration: a new stream is a new `correlation_id` value, not a new table.

**Testing**: pytest — unit, component, conformance (`tests/conformance/mcp`, `mcp_served`), plus
the served-surface check that this feature's own finding was made with.

**Target Platform**: Linux containers under Nomad; API and MCP surfaces.

**Project Type**: Governed agent runtime — sealed core plus transport surfaces.

**Performance Goals**: No latency target changes. The relevant constraint is **write volume**: seven
operations gain one append each. `list_runs` is the highest-frequency of them, and the coverage
rule was drawn (clarify Q1) specifically to keep the two highest-frequency catalogue reads out.

**Constraints**: The audit trail is append-only and never sampled (Principle IX), so entry volume
is permanent and cannot be tuned down later. The pinned entry digest in `test_audit_chain.py` must
not move. `get_run_result`'s subject-only restriction must not change (FR-015).

**Scale/Scope**: 17 operations classified; **7** gain records; 2 pinned as deliberately unrecorded;
**4** new audit event types; 1 ADR amended.

## Constitution Check

*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md).*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | No framework enters core. The new members live in `core/audit/schema.py`, which imports nothing new; recording happens in the shared surface functions both transports already call. |
| II — Total Interception; One Governed Tool Layer | **Pass** | No tool, registry, or hook path is touched. The seven operations are already fully intercepted for *authorization*; this adds a record, not a decision. |
| III — Fail-Closed, In-Process Enforcement | **Pass, and implicated.** | FR-007a makes a read's own audit write **enforcement rather than observation**: an unrecordable read fails and returns nothing. This matches both existing precedents (`start_governed_run`, `_record_access`). **Research F7 found the existing precedent's raise has no transport parity** — it raises `HTTPException` from shared code that MCP does not catch. 022 introduces a core error instead, so the new sites fail identically on both surfaces. **The same posture binds `stop_run`**: a stop whose entry cannot be written must not stop the run, matching `start_governed_run`, which already refuses when its own audit write fails. |
| IV — Zero Standing Credentials; Authority Per Task | **Pass** | No new credential, no new authority, no widening. A read record is written under the same sink the operation's surface already holds; the read itself is authorized exactly as it is today (FR-015 forbids re-scoping). Nothing here lets an agent — or a reader — exceed what they could already do. |
| V — Sealed Core, Versioned Seams | **Pass, review required.** | **Four** additive `AuditEventType` members: `RECORD_READ`, `RECORD_READ_REFUSED`, `THREAD_CREATED`, `RUN_STOPPED`. The fourth was added by analysis pass 8, which found `stop_run` writes nothing at all — a person terminating a run left no trail entry, and the spec had asserted the opposite as measured. Additive-only, no member removed or renamed, no existing payload shape changed. The pinned digest proves no written entry's hash moves (F5). **This PR must carry a security review request** — sealed core is not dischargeable by the author alone. |
| VI — Lean by Default | **Pass** | No new dependency, service, table, or migration. A new stream is a new `correlation_id` value. |
| VII — Anti-Fragmentation | **Pass, and it is the design.** | The recording shape, the stable-per-tenant stream, the shape-not-rows payload, and the fail-closed write are all adopted from `surfaces/api/evidence.py` rather than reinvented. The one deliberate divergence — a *separate* stream — is argued in research F3 on volume profile, not convenience. |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | **N/A** | No model, no judge, no suite. Nothing is promoted. `OWED` stays empty; no eval gate row is added or moved. |
| IX — Evidence Over Claims | **Pass, and it is the point.** | The feature's subject is the trail's own completeness. FR-006 keeps content out of records; FR-005a keeps reads out of the chain being read; FR-011 makes the surfaces' claim checkable against behavior instead of asserted. |
| X — The Decision Record Governs | **Pass, conditional.** | **ADR-0035 must be amended in this same change** (FR-012). Its text scopes "evidence access is itself audited" to the audit plane; 022 extends that discipline to records about runs and threads. Shipping the extension while the ADR describes the narrower scope would put the decision record behind the system. The amendment must also carry forward the separate-stream safeguard, now load-bearing for a second reason (FR-005a). |

**Gate result**: **PASS — proceed to Phase 0.**

**Two obligations this gate creates, recorded so they cannot be discharged by forgetting:**

1. **Security review request on the PR** (Principle V). Sealed core.
2. **ADR-0035 amendment in the same PR** (Principle X). Not a follow-up.

**No blocking conformance row is added that no automated check executes**, so the "name who runs
it before merge" clause does not bind. Every row this feature adds runs in `make check` or
`make conformance`.

## Project Structure

### Documentation (this feature)

```text
specs/022-audited-reads/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   └── conformance.md   # Phase 1 — the rows this feature binds
├── checklists/
│   └── requirements.md
├── spec.md
└── tasks.md             # /speckit-tasks — not created here
```

### Source Code (repository root)

```text
src/
├── core/
│   └── audit/
│       └── schema.py            # +4 additive AuditEventType members (SEALED CORE)
├── surfaces/
│   ├── api/
│   │   ├── record_access.py     # NEW — the reader stream, the write, the core error
│   │   ├── runs.py              # list/detail/result record before returning; stop_run_for writes RUN_STOPPED
│   │   ├── threads.py           # create/list/detail: record; THREAD_CREATED alongside THREAD_DELETED
│   │   └── evidence.py          # adjacent (F7): raise the core error, not HTTPException
│   └── mcp/
│       ├── operations.py        # McpOperation gains a required audit_disposition field
│       ├── transport.py         # map the core error to a 503 verdict matching the API
│       └── served.py            # governance sentence DERIVED from dispositions
docs/adr/
└── 0035-estate-state-queries-and-audit-read-path.md   # amended (Principle X)

tests/
├── unit/
│   └── test_audit_chain.py      # pinned digest row grows by three members
├── component/
│   ├── test_operations_audited.py   # unchanged in job; renamed or documented (see below)
│   └── test_record_access.py        # NEW — content exclusion, refusals, fail-closed
└── conformance/
    └── mcp/                     # parity across both surfaces, including the failure path
```

**Structure Decision**: Recording lives in the **shared surface functions both transports already
call** (`surfaces/api/runs.py`, `surfaces/api/threads.py`), not in either transport. Research F6
measured that `transport.py::_list_runs` imports and calls `runs.py::list_runs_for`; recording
there makes FR-008's parity structural rather than a property of two implementations agreeing.

A new `surfaces/api/record_access.py` holds the stream name, the write, and the core error, mirroring
`evidence.py`'s role for the evidence plane. It is a sibling, not a shared abstraction over both —
extracting a common base for two streams with different volume profiles and different ADR scopes
would be the kind of premature unification Principle VI warns about.

**On `test_operations_audited.py`**: its name reads like it covers this feature and it does not — it
asserts unauthenticated refusal. It keeps its job; the plan's obligation is that its **name or its
docstring stop implying coverage it never had**, because that misdirection is a measurable
contributor to this gap surviving seventeen operations. Renaming a file is cheap; leaving a trap
named after the thing it does not check is not.

## Constitution Re-Check (post-Phase 1)

**Re-evaluated after `data-model.md`, `contracts/conformance.md`, and `quickstart.md`. Still
PASS — no verdict moved.** What the design work changed is the weight on two rows, not their
outcome:

- **III — Fail-Closed** got *harder*, not easier. The data model's ordering constraint — the
  record is written **before** the records are returned — was implicit in FR-007a and is now
  explicit, because a read that answered first and recorded second would produce the unrecorded
  answer this feature exists to end, on any failure between the two.
- **X — The Decision Record** got a second obligation. Research F3's separate-stream decision has
  a consequence worth naming in the ADR-0035 amendment rather than leaving to discovery: an
  auditor asking "who looked at anything in this tenant" now queries **two** streams. That is the
  price of keeping deliberate evidence reads legible under routine listing volume, and the
  amendment must say so.

**No new principle became implicated.** Phase 1 added no dependency, no table, no credential, and
no authorization change.

**Analysis pass 2 added one measured fact the gate should hold against** (research F9a): the new
stream is reconciled like every other, and reconciliation writes its summary to a third stream
under `__platform__`, so sweeping `record-access` does not grow it. This matters to **Principle IX**
— a record of who looked, exempt from the check that its two copies agree, would be the one stream
nobody verifies. No verdict moves; the row is simply now covered by argument as well as by default
behavior.

**One thing the design surfaced that the gate should hold against, recorded here so it is not
lost in tasks**: `tests/component/test_operations_audited.py` keeps its job and must stop implying
coverage it never had. Leaving a file named for the check this feature adds, next to the feature
that adds it, is how the next reader concludes the question is already covered.

## Complexity Tracking

*No Constitution Check violations. Table intentionally empty.*

One judgment call worth recording even though it is not a violation:

| Decision | Why | Simpler alternative rejected because |
|---|---|---|
| A second stream (`record-access`) rather than reusing `evidence-access` | Volume profile: deliberate evidence reads vs. an editor's idle `list_runs` polling | One stream is simpler and genuinely tempting, but the trail is never sampled — routine listing noise would permanently bury the high-signal evidence reads in the stream an auditor opens first |
| Deriving the governance sentence from dispositions rather than testing a literal against them | FR-011 must fail when the claim overclaims | A test comparing the hand-written sentence to a second hand-written expectation would have passed every day this gap existed; keeping them in sync is the thing that failed |
