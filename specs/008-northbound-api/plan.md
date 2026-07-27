# Implementation Plan: Northbound API

**Branch**: `spec/008-northbound-api` | **Date**: 2026-07-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/008-northbound-api/spec.md`

## Summary

Build the first of ADR-0033's four transports: an HTTP surface that authenticates humans
against the organization's OIDC provider and machines by workload identity federation,
starts governed runs and returns a handle, and exposes the audit plane as a governed
read path.

The surface itself is thin. What makes this feature large is a prerequisite the spec
assumes and no prior feature built: **audit today is in-memory and queryable only by
correlation ID.** `InMemoryAuditSink` is the only implementation, `AuditSink` exposes
`append` and `list_by_correlation_id`, and there is no audit table in
`src/core/durability/schema.sql`. FR-008 asks the API to read the audit trail, and there
is presently no audit trail to read once a run's process exits. Durable, queryable
evidence is therefore in scope here, and is the largest single piece of work.

Two design commitments carry most of the weight:

**The read path cannot mutate, enforced by the database rather than by our care.**
ADR-0035 calls this "an implementation property to prove rather than assert." Evidence
reads use their own Vault dynamic role holding `SELECT` and nothing else, so an attempt
to write through the read path is refused by Postgres. The read seam is also a separate
Protocol with no write methods — mutation is absent from the type, not merely
unimplemented. Two independent mechanisms, because the first one is the one that gets
refactored away.

**The surface never learns what the substrate is.** Starting a run is a `RunDispatcher`
seam, exactly as durability is a provider seam (ADR-0024). Under the enclave a run is a
Nomad allocation; the API does not know that. A surface that submitted a jobspec directly
would make Principle VII's "substrate is the only permitted delta" false at the very
layer the customer touches first.

## Technical Context

**Language/Version**: Python 3.12+. `src/core` continues to import no framework;
`src/surfaces` imports the core, never the reverse

**Primary Dependencies**: **New, and the first new runtime dependencies since 005.**
FastAPI + Starlette + uvicorn for the transport, PyJWT + cryptography for OIDC token
verification. All permissively licensed and already clearable by
`licenses/allowlist.txt`. Justification and the rejected alternatives are in
[research.md](./research.md) — the short version is that FastAPI derives its OpenAPI
document from the same signatures and Pydantic models that validate requests, which is
FR-012's "generated from the implementation rather than maintained beside it" obtained
structurally, and that hand-rolling JWT signature verification is not a thing to do

**Storage**: Postgres, via the tables 005 already established plus a new evidence
schema. Two Vault dynamic roles against the same database: the existing run role, and a
new **evidence role holding `SELECT` only**

**Testing**: `pytest`, hermetic for the surface's own logic; enclave-marked for anything
touching real Vault, real Postgres, or a real allocation. The OIDC provider is the one
component correctly faked — it is outside our boundary, and we do not deploy it. The
double must run real OIDC flows and sign real JWTs with a real key, or this feature's
central guarantee ships unproven

**Target Platform**: A long-lived container in the enclave, holding its own attested
workload identity. It is a Nomad allocation like anything else, and holds no standing
credential

**Project Type**: Northbound surface. Thin glue over the governed core (Principle I),
plus the evidence persistence the core was missing

**Performance Goals**: None specified, and deliberately not invented. The one shape that
matters is structural rather than numeric: run start returns a handle and never blocks
(FR-007a), so a surface request's latency is unrelated to a run's duration

**Constraints**: Fail closed on absent, expired, unverifiable, or unmapped identity
(FR-005/006/016). No static credential anywhere (FR-003). Nothing may pause a run
(FR-015). The read path cannot mutate (FR-009). No route may expose direct tool
invocation (FR-007)

**Scale/Scope**: One enclave, one tenant. The tenant *dimension* is enforced from the
first commit even though one value is configured — see below

### Three things the spec assumes that do not exist yet

Stated up front because each is real work, and because a plan that discovered them during
implementation would be a plan that mis-sized the feature.

1. **There is no durable audit store.** Covered above. Roughly half this feature.

2. **There is no tenant.** `tenant` appears nowhere in `src/` or `tests/`, yet ADR-0035
   says the read path is tenant-scoped and FR-011 requires a cross-tenant query to return
   nothing distinguishably. The resolution is a single `tenant_id` on the authenticated
   subject, sourced from an IdP claim, enforced as the outermost dimension of every
   evidence query — with one tenant configured. This is **not** multi-tenancy, which 006
   put out of scope and which means isolating runs, storage, and policy. It is the
   evidence-scope dimension FR-011 requires, enforced now so that multi-tenancy later
   populates a check that already runs rather than adding an enforcement point to a system
   that never had one. A dimension introduced with the check is cheap; a dimension
   retrofitted across an existing evidence store is not.

3. **There is no way to start a run from outside a Python process.** `start_governed_run`
   is a function call. FR-007a needs a dispatch seam. Hence `RunDispatcher`.

### What this feature does not get to claim

FR-014 refuses the four-transport parity row, and the plan holds that line. With one
transport there is nothing to compare, and a green row would be exactly the stub ADR-0047
forbids. What this feature owes instead is making the comparison possible later: a
committed snapshot of the operation set and its verdicts, diffed by a check, so the second
transport compares against something recorded rather than against whatever the first
happens to do by then.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*
*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md)
— **checked against v1.1.0**; re-check if the version advances.*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | Pass | Adopt an HTTP framework and a JWT library rather than building either. The surface maps requests onto core machinery and adds no decision of its own. Not a gateway product (ADR-0008): this is the platform's own front door, not a proxy sold to front other people's APIs |
| II — Total Interception; One Governed Tool Layer | **Pass, and this is the feature's spine** | FR-007 forbids exposing tool invocation at all — a caller reaching a tool through the API would be acting beside the agent rather than through it. Asserted by walking the app's routes, not by review |
| III — Fail-Closed, In-Process Enforcement | Pass | Absent, expired, unverifiable, and unmapped identities all refuse with nothing executed. Enforcement stays in the governed core; the surface is a client of it, never an enforcement point |
| IV — Zero Standing Credentials; Authority Per Task | **Pass, and most exercised here** | No static keys, no credential store, no exception. The API process itself holds an attested workload identity and draws dynamic database credentials per its own lifecycle — including the SELECT-only evidence role |
| V — Sealed Core, Versioned Seams | **Pass, with the review this requires** | Two sealed-core changes: new `AuditEventType` members for evidence access, and a new `EvidenceQuery` seam. Both purely additive — no existing seam changes shape. Sealed-core changes need security-maintainer review per the Development Workflow and CODEOWNERS |
| VI — Lean by Default | Pass, with the trigger named | An API server is an additional operated component; its named trigger is ADR-0033, Accepted. The new libraries are libraries, which is what this principle asks for rather than forbids |
| VII — Anti-Fragmentation | Pass | The `RunDispatcher` seam is what keeps this true. The surface is identical on every substrate because it never learns which one it is on |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | N/A | No packs, prompts, models, or policies promoted |
| IX — Evidence Over Claims | **Pass, and load-bearing** | This feature *is* the evidence read path. Reading evidence is itself an auditable act (FR-010), and a cross-tenant query must be distinguishable from a legitimately empty one (FR-011) — an investigator needs to tell "nothing happened" from "you may not see it" |
| X — The Decision Record Governs | Pass | Implements ADR-0033 and ADR-0035; binds ADR-0016 (FR-013) and ADR-0015. Cites ADR-0049 as **Proposed**, which is why FR-015 forbids pausing rather than defining a pause |

**Gate result**: PASS — proceed to Phase 0

### Post-design Constitution Check

Re-checked after Phase 1: still **PASS**. Four notes for review:

- **Principle V carries the risk this time.** 007's core addition was one small observation
  seam. This one touches the audit schema, which is the store every other guarantee is
  reconciled against. Both changes are additive and neither reshapes an existing seam, but
  "additive" is a claim to check in review rather than accept in a plan.

- **Principle IX has a failure mode worth naming.** Meta-auditing evidence access means
  reading the audit trail writes to the audit trail. Reading the meta-audit records then
  writes more. This terminates because a read produces exactly one record regardless of how
  many rows it returned, but it is the kind of thing that is obvious once stated and
  expensive once shipped wrong.

- **Principle IV's hardest line is FR-003, and it is a negative.** "No supported
  configuration creates a static credential" cannot be proven by a passing test; it is
  proven by enumerating every authentication path and asserting what is absent, in the
  shape 007's `test_no_run_interrupt.py` used for its own negative requirement — matching
  against code with comments stripped, because prose about API keys is not an API key.

- **Principle II's assertion must walk routes, not grep.** The check that no route reaches
  a tool has to enumerate the application's registered routes and inspect what they call.
  A text search would pass a file that mentions `invoke_tool` in a docstring and miss one
  that reaches a tool through an alias.

## Project Structure

### Documentation (this feature)

```text
specs/008-northbound-api/
├── plan.md                        # This file
├── research.md                    # Phase 0 — dependency and design decisions
├── data-model.md                  # Phase 1 — entities and the evidence schema
├── quickstart.md                  # Phase 1 — how to run and validate it
├── contracts/
│   ├── api-surface.md             # Operations, the description, and what parity will compare
│   ├── evidence-read-path.md      # The read seam and its two mutation defences
│   └── conformance-api.md         # Rows in force, and the row this feature refuses
├── checklists/requirements.md
└── tasks.md                       # /speckit-tasks output — not created here
```

### Source (repository root)

```text
src/surfaces/
├── __init__.py                    # Exists as a stub; gains the app factory
├── api/
│   ├── app.py                     # Application assembly; routes registered here only
│   ├── identity.py                # OIDC verification, workload identity federation
│   ├── claims.py                  # Claim-to-role mapping (governed configuration)
│   ├── runs.py                    # Start / query — returns a handle, never blocks
│   ├── evidence.py                # The governed read path
│   └── description.py             # Operation description generated from the app
└── dispatch/
    ├── types.py                   # RunDispatcher protocol
    ├── inprocess.py               # For hermetic tests
    └── nomad.py                   # The real one — a run is an allocation

src/core/audit/
├── schema.py                      # + EVIDENCE_READ, EVIDENCE_READ_REFUSED (additive)
├── query.py                       # EvidenceQuery protocol — read only, by construction
├── postgres.py                    # Durable AuditSink + EvidenceQuery implementation
└── evidence_schema.sql            # Audit tables; SELECT granted to the evidence role

infra/modules/trust-fabric/
└── database.tf                    # + the evidence dynamic role (SELECT only)

tests/
├── unit/                          # Claim mapping, scope algebra, description snapshot
├── component/                     # Surface behaviour against fakes
├── conformance/api/               # The rows this feature puts in force
└── harness/
    └── fake_oidc_provider.py      # Real flows, real signatures — outside our boundary
```

**Structure Decision**: `src/surfaces/api/` under the existing stub package, with the
dispatch seam beside it rather than inside it — the CLI and portal specs will need the same
seam, and putting it under `api/` would make the second transport import the first, which
is the coupling this feature exists to prevent. Audit persistence lands in `src/core/audit/`
because it is core, not surface: the evidence store belongs to the platform whether or not
anyone ever reads it through HTTP.

## Complexity Tracking

No Constitution Check violations to justify. Two entries recorded because they are
genuine additions rather than violations, and a later reader should find the reasoning
here rather than reconstruct it.

| Addition | Why needed | Simpler alternative rejected because |
|-----------|------------|-------------------------------------|
| Durable audit store (`src/core/audit/postgres.py` + schema) | FR-008 requires reading the audit trail; today it exists only in the memory of a running process | Reading `InMemoryAuditSink` would work only for runs that have not finished, which is the opposite of what an audit trail is for |
| New runtime dependencies (FastAPI, PyJWT + cryptography) | An HTTP surface and verified OIDC tokens | Stdlib `http.server` gives no ASGI, no request validation, and no generated description, so FR-012 would become a hand-maintained document — the exact thing FR-012 forbids. Hand-rolling JWT verification means hand-rolling signature checking, which is how this goes wrong quietly |
