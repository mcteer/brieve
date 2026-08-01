# Implementation Plan: The MCP surface gets a server

**Branch**: `spec/019-mcp-server` | **Date**: 2026-07-31 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/019-mcp-server/spec.md`

## Summary

Serve the transport that has been correct for four features and reachable by nobody.
`McpTransport` executes every operation against the governed core and is constructed nowhere
in the shipped source; no protocol framing exists in the tree. A new served process
constructs it from real collaborators, speaks the protocol over a socket a client can attach
to, carries the calling user's identity across the boundary, and is proven by conformance rows
driven through the **running process** rather than through a fixture.

**Phase 0 overturned the spec's central assumption, and it changes the shape of the work.**
Host-mode ports are not reachable from the developer's machine — measured, with the API
answering 200 inside the VM and nothing on macOS. So the reachability half is real work rather
than a formality, and per the clarification it stays in scope. The mitigating finding is that
the fix is a pattern already proven in this repository: `postgres` and `collector-postgres` run
in bridge mode with mapped ports and the host lanes reach them on every run. **The new surface
is born in bridge mode rather than converting anything that works today.**

## Technical Context

**Language/Version**: Python 3.12, as the rest of `src/`.

**Primary Dependencies**: `mcp==1.28.1` — already declared, imported nowhere. Used for both the
server and, per SC-001, the acceptance client. **No new dependency is added by this feature.**

**Storage**: None new. The served process reaches the same Postgres-backed stores the API
reaches, through the same collaborators — but it **addresses** them differently, because it
runs in bridge mode. The host is passed at construction, which every one of those collaborators
already accepts as a keyword argument and which `src/surfaces/api/service.py` already does.

**No `src/core/` module changes, and this was nearly wrong.** The first task list proposed
adding an environment-driven host to four core modules, which would have made the Principle V
verdict below false — Principle V names *audit schema* and *durability* as sealed core and
requires security-maintainer review for changes to them. The seam already existed and was
merely unused from an assembly. Caught by analysis pass 1.

**Testing**: `pytest`. A new `tests/conformance/mcp_served/` driven against the running process
in the `host_enclave` lane — distinct from `tests/conformance/mcp/`, which exercises the
transport class and stays exactly as it is.

**Target Platform**: The enclave. A Nomad job on the dev substrate, reachable from macOS.

**Project Type**: Service — a second front door onto an existing core.

**Performance Goals**: None stated and none invented. This surface serves a developer's IDE,
not a fleet. Session establishment must not be so slow a client times out; nothing beyond that
is a requirement, and inventing one would impose a constraint nobody asked for.

**Constraints**: The served transport and the supervisory loop MUST be independently available
(FR-015a). The subject is fixed per session, the credential re-checked per operation (FR-013a
with FR-013). No operation may be served by protocol-layer logic reaching the capability
directly (FR-005).

**Scale/Scope**: One new served process, one new job, one new conformance directory. The
transport class, its operations, and its fifty-six existing rows are unchanged.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — see below.*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | The protocol framing is the SDK's. This feature writes assembly and identity plumbing, which is what glue is. It adds no capability. |
| II — Total Interception; One Governed Tool Layer | **Pass** | FR-005 and FR-006 are this principle restated for a new door: every operation through the governed core, and the protocol layer may report a refusal but never author one. |
| III — Fail-Closed, In-Process Enforcement | **Pass** | FR-003 refuses to start when collaborators are missing; FR-012 refuses before the governed operation is entered. Both fail closed. |
| IV — Zero Standing Credentials; Authority Per Task | **Pass** | FR-013 forbids a session outliving the credential that opened it — "no standing authority" applied to a long-lived connection, which is precisely where it would otherwise erode unnoticed. |
| V — Sealed Core, Versioned Seams | **Pass** | The core is untouched — **verified against the task list, not assumed**. Every collaborator the new assembly needs already exposes the configuration seam it requires; nothing in `src/core/` is edited. This attaches at the transport seam ADR-0033 defines. |
| VI — Lean by Default | **Pass** | No new dependency. One new process, required by FR-015a rather than preferred — see Complexity Tracking. |
| VII — Anti-Fragmentation | **Pass** | The opposite of fragmenting: two surfaces exist and only one is served, so *served* behaviour has only ever been one surface's. FR-008 checks the operation sets match mechanically rather than by inspection. |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | **N/A** | Promotes no pack, model, or policy. |
| IX — Evidence Over Claims | **Pass** | The whole feature. FR-004 and FR-016 forbid asserting against a constructed object what is owed about a running service; FR-011 requires two callers be *distinguishable*, because "a subject was recorded" passes against a shared account. |
| X — The Decision Record Governs | **Pass** | ADR-0033 and ADR-0048 are implemented, not amended. No new ADR is needed — this builds what a record already decided. |

**Quality Gates — who runs what.** Every row this feature adds is executed by an automated
check. **No named human runner is owed for the rows** — and that sentence is true of the rows
and of nothing else, which an earlier draft of this plan did not say.

Three things here are **not** rows and each needs a person:

| | What it is | Who |
| --- | --- | --- |
| FR-017's demonstration | A credential that must be refused, observed refused *by the core* | The implementer, once, against their own enclave |
| **SC-006 / FR-015** | Someone follows the written setup from nothing and connects | The implementer, once — **T034a** |

The constitution is explicit that a blocking row no automated check executes MUST have a named
party responsible before merge. SC-006 and FR-015 are human-judgement criteria that no row can
evaluate; SC-006 was tagged onto an automated reachability row, so nominal coverage read 100%
while nothing assessed it. Found by analysis pass 5.

**Gate result**: **PASS — proceed to Phase 0**

**Re-check after Phase 1 design**: **PASS**, unchanged. One item was added to Complexity
Tracking during design — the second job — and it is required by FR-015a rather than chosen.

## Project Structure

### Documentation (this feature)

```text
specs/019-mcp-server/
├── plan.md                   # This file
├── research.md               # Phase 0 — the reachability measurement and what it overturned
├── data-model.md             # Phase 1
├── quickstart.md             # Phase 1
├── contracts/
│   ├── served-surface.md     # What a client may rely on
│   └── conformance.md        # The rows, and the limits recorded as prominently
├── checklists/
│   └── requirements.md       # From /speckit-specify
└── tasks.md                  # /speckit-tasks — not created here
```

### Source Code (repository root)

```text
src/surfaces/mcp/
├── transport.py              # UNCHANGED — the class that has been correct all along
├── operations.py             # UNCHANGED — the operation set
├── health.py                 # UNCHANGED
├── server.py                 # UNCHANGED — keeps the supervisory loop, loses nothing
└── served.py                 # NEW — protocol framing, session identity, assembly

infra/jobs/
├── mcp.nomad.hcl             # UNCHANGED in function — the supervisory loop keeps its home
└── mcp-surface.nomad.hcl     # NEW — bridge mode, mapped port, reachable from macOS

infra/bin/
├── mcp-surface-up            # NEW — bring the surface up; reads .env with enclave-up's fallbacks
└── mcp-surface-conformance   # NEW — 017's lifecycle: bring up, mark, run, tear down

src/core/                     # UNCHANGED, and checked rather than assumed — see below

tests/conformance/mcp_served/
├── __init__.py
├── surfaces.py               # NEW — reaching the served process, as 017's surfaces.py does
├── conftest.py               # NEW
└── test_*.py                 # NEW — rows driven through a real client over a real socket

tests/conformance/mcp/        # UNCHANGED — 56 rows against the class, still meaningful
```

**Structure Decision**: a new module beside the transport rather than inside it, and a new job
beside the supervisory loop rather than inside it.

The module split follows what each thing is. `transport.py` executes operations against the
core and knows nothing about protocols or sockets — which is why it stayed correct while
unserved. `served.py` owns framing, session identity, and assembly: the three things with no
coverage today. Putting framing inside `transport.py` would give fifty-six existing rows a
protocol dependency they do not need and cannot exercise.

The job split is FR-015a satisfied structurally rather than by care. See Complexity Tracking.

## Phase 1 outputs

- [data-model.md](./data-model.md) — session, subject, and the operation envelope. The state
  transition that matters is *session established* → *credential lapsed*, because it is the one
  a naive reading of FR-013a would get wrong.
- [contracts/served-surface.md](./contracts/served-surface.md) — what a client may rely on.
- [contracts/conformance.md](./contracts/conformance.md) — the rows, who runs them, and what
  they refuse to assert.
- [quickstart.md](./quickstart.md) — bring it up, attach a client, watch a refusal.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| A second long-running process (`mcp-surface` alongside `mcp`) | **FR-015a** — the served transport and the supervisory loop must be independently available. The loop is what resumes suspended runs; a protocol crash that stopped it would present as a hang while quietly ending ADR-0049's guarantee that consent to start a run is consent to finish it. | **One process, two concerns, careful exception handling**: rejected because it makes the guarantee depend on catching everything, and FR-015a exists because nobody can. **In-process supervision and restart**: rejected as more machinery than separation, failing in exactly the way it is meant to prevent. Separation is also what ADR-0025 prefers generally — structure over runtime care. |
| A new conformance directory rather than rows added to `tests/conformance/mcp/` | Those rows exercise the transport **class** and must keep doing so. They are not wrong; they are narrower than they read. Rows driven through a running process need a lane that brings that process up, which the class rows must not require. | **Adding served rows to the existing directory**: rejected because it would put a live-service dependency on fifty-six rows that correctly have none, and would slow the fast lane for no gain. |

**Not violations, named so they are not mistaken for any**: this feature adds no dependency, no
ADR, and no operation. The transport's surface area is unchanged. What changes is that
something serves it.

## Two things carried into tasks

**The `mcp` job's name describes a surface it does not serve, and it keeps that name anyway.**
With a second job arriving, two honest names would be better. They are not worth what they
cost: `infra/modules/trust-fabric/variables.tf` defaults the bound job name to `mcp` and
`auth.tf` defines `vault_jwt_auth_backend_role "mcp"`, so **the allocation's workload identity
binds on that name** — renaming without re-binding leaves the supervisory loop unable to
authenticate, which is a defect shape the API has already paid for once. A durability row
hardcodes `nomad job status mcp` as well.

An earlier draft of this plan carried the rename into tasks with its cost stated as "a
deployment change, not a rename." That understated it, and a task whose stated cost is
stopping a job while its real cost includes re-binding a Vault auth role is worse than one
that is missing, because it reads as safe. **T036 now records the bindings instead**, so a
future rename starts from a list rather than from a surprise. Found by analysis pass 3.

**A new conformance directory must be named by a lane that selects its markers.** 018 shipped
rows no lane collected while its contract asserted otherwise. That is now caught automatically
by `tests/unit/test_every_conformance_directory_is_run.py`, which is why this note is a
reminder rather than a risk.
