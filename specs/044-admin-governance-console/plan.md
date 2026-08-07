# Implementation Plan: The admin console — governance configuration leaves Terraform

**Branch**: `spec/044-admin-governance-console` | **Date**: 2026-08-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/044-admin-governance-console/spec.md`, measured
against `d30f771` plus this branch.

## Summary

An administrator reads the platform's governance posture and requests changes to it from a
portal page; the trust fabric decides. Three record families are writable — the ask-bindings
(including the judge toggle), claim mappings, and a new product-connections record — through
the existing three-outcome submitter, generalised. The `admin` role is disjoint from the two
that exist; a dispatched run cannot reach any of it; and the toggle's semantics — disclose,
never suppress — are settled as the template for every toggle after it.

**The finding that shapes the plan** (research R1): the request-and-decide mechanism has no
deployed principal. No policy grants write on any `harness-authority` path, `authority_change`
is attached to no role, and the submitter is constructed without a token — so the "existing
governed write path" works in rows and has never once been exercisable in a deployment. 044's
first job is to give the mechanism a principal: an `authority_submit` grant on exactly the
console's records, attached to the API's attested identity, Control-Group-gated where a quorum
is configured.

## Technical Context

**Language/Version**: Python 3.12 (uv-managed), matching the tree

**Primary Dependencies**: none added. Portal pages are server-rendered templates through the
existing relay; fabric writes ride `authority_submit.py` generalised; probes use stdlib urllib

**Storage**: the trust fabric — `ask-bindings` (+`relevance_enabled`), `claim-mappings/*`,
`product-connections` (new), the `authority_submit` policy and `controlled_paths` extension;
the audit trail for reads, requests, decisions, refusals

**Testing**: pytest — unit + hermetic conformance (C1–C25); `enclave`-marked CL1–CL2
fail-not-skip; the a11y lane gains `/settings` (CL3). Named runner: Dan

**Target Platform**: the enclave; portal + API served processes

**Project Type**: single project — additions in `src/surfaces/{portal,api}`,
`src/core/answering` (toggle semantics), `infra/modules/trust-fabric`

**Performance Goals**: console reads are a handful of fabric reads per page; zero added reads
on the answering path (the toggle rides the binding record already read per ask)

**Constraints**: pending ≠ applied, rendered and asserted; no restart for any change
(placement, not machinery — R4); no credential enters or leaves through the console; the
interface holds no governance logic

**Scale/Scope**: 1 new role key, 1 new record, 1 record field, ~4 API routes, 1 portal page,
1 trust-fabric policy + `controlled_paths` extension, ~25 conformance rows, ADR-0069

## Constitution Check

*Named-runner obligation*: CL1–CL2 and the enclave rows have no automated runner. **Dan runs
them before merge**; the contract records this.

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | The approval workflow is Vault's Control Groups, consumed not rebuilt; the console renders decisions. No approval UI (R11) |
| II — Total Interception; One Governed Tool Layer | **Pass** | No new tool, no new transport verb; portal-only per Q1, with C22 asserting MCP's absence. The portal stays a thin client — the relay remains its one door |
| III — Fail-Closed, In-Process Enforcement | **Pass** | Unreadable config renders unavailable, never default (C10); a change that cannot be validated never reaches the fabric (C1); the submitter maps refusal as refusal (C4/C8) |
| IV — Zero Standing Credentials; Authority Per Task | **Pass** | The submitter runs under the API's attested identity — R1 rejects both a configured token and a console service identity. Admin is granted through the gated mapping path and cannot be self-granted (C21). A dispatched run is structurally excluded (C19/C20). No credential is entered or displayed (FR-018b, C25) |
| V — Sealed Core, Versioned Seams | **Pass** | `Answer`/ask-path changes are additive (disposition + note reuse 043's fields); `ROLE_VISIBILITY` gains a key; the binding parser gains one defaulted field (C18 keeps old records meaning what they meant) |
| VI — Lean by Default | **Pass** | No new operated component, no dependency; the probe is urllib; one new KV record |
| VII — Anti-Fragmentation | **Pass** | One submitter generalised rather than a second write mechanism; identical across substrates |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | **Pass** | The console can only bind cells the matrix qualifies (C1/FR-009) — it makes ungated promotion *harder* to do by accident, not easier. No model output is produced |
| IX — Evidence Over Claims | **Pass** | Reads audited (EVIDENCE_READ precedent), every request/decision/refusal recorded, pending never rendered as applied (C2), verification never folded into acceptance (C24). The disabled gate writes no MODEL_GATE — no event for a gate that did not run |
| X — The Decision Record Governs | **Pass** | ADR-0069 (new, Proposed) records the deliberate move of 026's governance/assembly line; ADR-0039 presented, not widened (R7); ADR-0016 consumed |

**Gate result**: **PASS — proceed** (re-checked post-design; verdicts unchanged)

**The argued posture change, stated rather than slipped**: 026 rejected deployment config
because *which model is permitted* is governance. 044 does not reverse that — it moves the
*origination* of a governance change to a person without estate credentials while leaving the
*decision* in the trust fabric, gated, recorded, and refusable. ADR-0069 is where that
argument lives, and the Complexity row below carries what was declined.

## Project Structure

### Documentation (this feature)

```text
specs/044-admin-governance-console/
├── plan.md              # This file
├── research.md          # R1–R12
├── data-model.md        # GovernanceConfiguration, ConfigChange, AdminRole, GateToggle, ProductConnection
├── quickstart.md        # Hermetic → the mechanism's first principal → the toggle end to end
├── contracts/
│   └── conformance-console.md   # C1–C25, CL1–CL3, named runner
└── tasks.md             # /speckit-tasks output (not created here)
```

### Source Code (repository root)

```text
src/
├── core/answering/
│   ├── scope.py                 # +"admin": frozenset() — disjoint (R6)
│   └── answer.py                # disabled-gate disposition + disclosure note (reuses 043 fields)
├── core/authority/ask_binding.py  # +relevance_enabled, absent = enabled (C18)
├── surfaces/api/
│   ├── authority_submit.py      # ConfigChange generalisation of the ClaimMapping submitter (R8)
│   ├── console.py               # NEW: /console routes — read, change request, verify (admin-only)
│   └── ask.py                   # toggle honoured before judge resolution (R4)
├── surfaces/portal/
│   ├── app.py                   # +/settings page through the relay
│   └── templates/settings.html  # NEW

infra/modules/trust-fabric/
├── control-groups.tf            # controlled_paths += ask-bindings, product-connections (C6)
├── authority-submit.tf          # NEW: the write grant with control_group when quorum set (R1)
└── policies.tf                  # harness_authority_read += product-connections (exact path — 042's lesson)

tests/
├── unit/                        # C3, C6, C18, role disjointness, record parsers
├── conformance/console/         # NEW: C1–C25 (C19/C20 beside the authoring exclusion rows)
└── a11y/                        # +/settings rows (CL3)

docs/adr/0069-*.md
```

**Structure Decision**: single project. The console route module is API-side because the
portal relays and never decides; everything governance-shaped lands in records and the fabric,
keeping the page dumb enough that C8 ("no apply path") is a fact about architecture rather
than discipline.

## Complexity Tracking

No Constitution Check violations. Two deliberate scope declinations, recorded:

| Declined | Why |
| --- | --- |
| The `research`/`validate` role names from the original ask | No capability exists behind them; a display alias would invite belief in one. The console presents ADR-0039's real names with descriptions (R7) — half the requested vocabulary, deliberately |
| Pack tool clients consuming `product-connections` | The record ships with two honest consumers (probe + display) and a visible "not yet consumed by dispatched runs" label; wiring every tool call to a fabric read to serve a record nothing needed yet is the Terraform leg's argument to make (R5) |
