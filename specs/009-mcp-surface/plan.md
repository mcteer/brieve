# Implementation Plan: MCP Surface

**Branch**: `spec/009-mcp-surface` | **Date**: 2026-07-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/009-mcp-surface/spec.md`

## Summary

Four things that belong together because they need each other, not because they are alike:
the MCP transport, ADR-0049's dependency health checks and resume sweeper, continuous
evidence-stream verification, and the CI lane that runs the enclave rows.

**The CI lane goes first**, and that is a real decision rather than sequencing hygiene.
Sixteen merge-blocking rows are currently protected by an instruction in `AGENTS.md`. This
feature then adds a sealed-core change, a constitution amendment, and a persistent service —
each of which is exactly the kind of change those rows exist to catch. Building the control
before the changes it must catch is the only order where the control is ever tested by
something it did not already pass.

**The constitution amendment is larger than one row, and finding that out took an analyze
pass.** Three places in the governing document describe behaviour this feature changes:

| Where | Says | Becomes |
| --- | --- | --- |
| Quality Gates, durability rows | "grant-expiry **parking**" | grant-expiry **stop** |
| Quality Gates, parity row | "surface parity across **all four** transports" | parity across **every pair of implemented** transports |
| **Principle VIII** | "or the run **parks**" | the run **stops**, reason recorded |

The parity one is the finding I would least like to have missed. This feature's spec argued
for *claiming* the four-transport row on the reasoning that refusing twice would be
avoidance — which is persuasive and does not survive reading the row, since two is not four.
Claiming it would have been the stub ADR-0047 forbids, in the feature whose spec makes a
point of refusing stubs. Amending it to bind incrementally is better than either claiming or
deferring: the gate then binds at two transports, at three, and at four, instead of sitting
inert until the last one lands.

**And the original one the spec did not anticipate.** The constitution's
Quality Gates name seven durability rows, one of which is **"grant-expiry parking"**.
ADR-0049 removes parking: grant expiry now *stops* the run with the reason recorded, the
same disposition as any other execution bound. So a named constitutional gate row changes
what it asserts, and that requires a constitution amendment with a Sync Impact Report — not
a quiet rename in a test file. Discovered by grepping for `PARKED` and finding it in
`tests/conformance/durability/rows.py`.

**The subtlety most likely to be got wrong** is not in any of the four pieces. ADR-0049
says an availability denial and a policy denial must stay distinguishable, and goes further
than the spec did: *only the availability class is model-visible as an invitation to adapt.*
A scope denial must not teach an agent to find another route — that is the governance
boundary holding. Blurring them "would teach agents that denials are obstacles to route
around, which inverts Principles II and III."

## Technical Context

**Language/Version**: Python 3.12+. `src/core` imports no framework; `src/surfaces` imports
the core, never the reverse

**Primary Dependencies**: The official **MCP Python SDK** (`mcp`, MIT), adopted rather than
hand-rolled — Principle I, and ADR-0033's "migrate onto official servers as they mature".
Everything else is present: FastAPI and PyJWT from 008, `pg8000` from 005

**Storage**: The Postgres 005 and 008 established. Dependency health records are new state
and live there; **health is not kept in memory**, because a restart of the service must not
silently mean "everything is reachable again"

**Testing**: `pytest`. Parity is asserted by driving both transports as one subject and
comparing verdicts and audit events. Dependency outages are simulated by making a fake
product unreachable — the product is outside our boundary and correctly faked; the
scheduler, Vault, and Postgres are not and are real

**Target Platform**: A **persistent** Nomad `service` job — the first in this platform.
Everything else is `batch` and ephemeral by design, which ADR-0049 makes part of the
guarantee. The asymmetry is the point: the sweeper and health checker need something that
outlives a run

**Project Type**: Second northbound transport, plus two platform mechanisms and a CI lane

**Performance Goals**: None numeric. The shape that matters: the health checker's interval
must be short enough that a recovered dependency resumes runs promptly and long enough that
checking is not itself load on a struggling product

**Constraints**: Parity asserted, not claimed (FR-003/004). Unknown health is unhealthy
(FR-006). Denial before execution, with no intent record (FR-007). Nothing waits on a human
(FR-014). The enclave lane must not run for forks (FR-019)

**Scale/Scope**: One enclave, one tenant, a handful of products

### What this feature changes that is not its own

Four, and each is a change to something a prior feature or the constitution owns.

1. **`RunState.PARKED` is removed** (FR-015), which is a sealed-core change touching 005's
   `run.py`, `checkpoint.py`, and `resume.py`, plus five test modules.
2. **The resume path needs a dispatch route that does not exist.** The sweeper starts a new
   allocation, and 008's `agent-run` parameterized job declares `meta_required` of
   correlation, subject, tenant, and definition — **no `run_id`, no `step_index`**. A resume
   needs both. Extending someone else's jobspec is a small change with a large failure mode:
   without it the sweeper can decide to resume and has nothing to resume with.
3. **Three constitutional passages change**, per the table above. One Sync Impact Report
   citing ADR-0049 and ADR-0033, naming each. A partial amendment leaves the governing
   document describing states that cannot occur, which is worse than not amending at all
   because it reads as deliberate.
4. **ADR-0049 stops being Proposed** (FR-021), and **ADR-0026 records being partially
   superseded by it**. Principle X requires superseding be recorded, never edited in place —
   an ADR silently outlived by another is the failure that principle names.

### The seams this feature extends, enumerated

Three analyze passes each found the same shape — a mechanism specified without the thing it
acts through — at a different layer. The generalisable cause is worth stating rather than
fixing case by case: **009 is the first feature to consume seams that 002, 005, and 008 built
for a single caller each.** None was designed to be extended later, so each accepts exactly
what its original caller passed and nothing more.

Enumerated here so implementation confirms rather than discovers:

| Seam | Owner | Accepts today | 009 needs | Task |
| --- | --- | --- | --- | --- |
| `GovernedRun` / `builtin_governance_hooks()` | 002 | No health reader; the factory takes no arguments | A path from a hook to dependency health | T032a |
| `RunDispatcher.dispatch()` | 008 | Five keyword arguments | Optional `run_id`, `step_index` for resume | T042a1 |
| `agent-run` jobspec `meta_required` | 008 | correlation, subject, tenant, definition | `run_id`, `step_index` | T042a |
| Vault JWT auth roles | 006 | `harness`, `conformance`, `agent-run`, per-agent | An `mcp` role | T022a |
| `verify_stream_integrity(conn_factory)` | 008 | A run-role connection factory | The MCP service to build one | T053b |

Each extension is **optional-by-default where a prior caller exists**, which is the rule that
would have prevented two of the findings on its own: a required parameter added to a seam
breaks the caller that was already using it.

**This table has itself been incomplete once** — the fourth analyze pass found
`verify_stream_integrity`'s connection factory missing from it, having found the class of
problem the table exists to record. An enumeration that reads as exhaustive and is not is
worse than none, so treat a new consumption of a prior feature's seam as a row to add here
rather than a detail to absorb into a task.

### The CI lane cannot be fork-safe, and that is not a compromise

It needs a Vault Enterprise licence, which is a secret. GitHub does not expose secrets to
workflows triggered by fork pull requests, and the mechanism that would — `pull_request_target`
— runs *base-branch* workflows with secrets available to code the fork controls. Using it
here would hand a licence and a live enclave to arbitrary pull requests, which is a worse
problem than the gap being closed.

So: the fast lane stays fork-safe and runs for everything; the enclave lane runs only for
pull requests whose head repository is this one. Fork contributors get the same fast lane
they get today, and their enclave rows are run by a maintainer — which is the current
situation for everyone, narrowed to a much smaller set of pull requests.

**This is a dependency on you rather than on the code**: the lane cannot be verified without
the licence in repository secrets, and I cannot provision that.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*
*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md)
— **checked against v1.1.0**; this feature amends it, so re-check against the amended text.*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | Pass | Adopt the official MCP SDK rather than implementing the protocol. ADR-0033 says to migrate onto official servers as they mature, and hand-rolling one would be the opposite |
| II — Total Interception; One Governed Tool Layer | **Pass, and the load-bearing row** | MCP reaches the same core as the API (FR-001), and the dependency refusal runs *inside* the pipeline (FR-009). A health pre-check beside the pipeline would be a second refusal path, which is a second authorization path wearing a practical-sounding name |
| III — Fail-Closed, In-Process Enforcement | Pass | Unknown health is unhealthy (FR-006). Denial precedes execution and writes no intent record (FR-007) |
| IV — Zero Standing Credentials; Authority Per Task | **Pass, with the honest caveat** | MCP acts as the calling user, never as itself (FR-002a). But a *persistent* service holds an identity for as long as it runs, which is closer to standing than anything shipped so far. It is mitigated rather than absent: the identity carries a TTL and is re-issued, and the service holds no product credential — it starts runs and reads health |
| V — Sealed Core, Versioned Seams | **Pass, and the heaviest review burden here** | `RunState.PARKED` is removed — not additive, touches 005's durability path, and changes what a constitutionally-named gate row asserts. Plus **four seams extended** (see the table above), including a new field on `GovernedRun`, which is 002-era sealed core. Every extension is optional-by-default so prior callers keep compiling. Security-maintainer review required |
| VI — Lean by Default | Pass, with triggers named | A persistent operated component needs a named trigger in an ADR. Two exist: ADR-0033 names MCP as a transport, ADR-0049 requires a long-lived home for the sweeper. Without ADR-0049 this would be a Principle VI failure |
| VII — Anti-Fragmentation | **Pass, and the CI lane is where it could break** | The lane must run `make conformance` — the same command a human runs — not a bespoke CI sequence. Two ways to run the gate is two gates, and the one nobody runs locally is the one that rots |
| VIII — Eval-Gated Promotion | N/A | No packs, prompts, models, or policies promoted |
| IX — Evidence Over Claims | **Pass, and doubly exercised** | Parity is asserted on audit equivalence (FR-003a), and the evidence trail is now verified while running rather than at bring-up (FR-017) |
| X — The Decision Record Governs | **Pass, and this feature is where a record resolves** | ADR-0049 stops being Proposed and ADR-0026 records being superseded by it (FR-021) — Principle X requires superseding be recorded, never edited in place. The constitution is amended in the same change as the ADRs it follows |

**Gate result**: PASS — proceed to Phase 0

### Post-design Constitution Check

Re-checked after Phase 1: still **PASS**. Four notes for review:

- **Principle VI deserves the closest look.** Every prior feature could say "no new operated
  component". This one cannot. The triggers are real and recorded, but "ADR-0049 needs a
  long-lived home" is an argument that would justify almost any service if applied loosely,
  and it should not be reused without the same scrutiny.

- **Principle IV's caveat is the one I would push back on if reviewing.** A persistent
  service is a persistent identity. The mitigations are genuine — TTL, re-issue, no product
  credential — but the honest statement is that this is the least ephemeral thing in the
  platform, not that it is as ephemeral as everything else.

- **Principle II's risk is a convenience refactor, not a design error.** The dependency
  check is *obviously* cheaper as a pre-flight before the pipeline, and it would work. The
  conformance row has to assert placement, not just behaviour, or the first person
  optimising a hot path will move it and nothing will notice.

- **Principle VII binds the CI lane specifically.** If the lane ends up running a bespoke
  sequence rather than `make conformance`, the two will drift and the local gate becomes
  advisory. The lane should be thin enough that its content is uninteresting.

## Project Structure

### Documentation (this feature)

```text
specs/009-mcp-surface/
├── plan.md                        # This file
├── research.md                    # Phase 0 — decisions and rejected alternatives
├── data-model.md                  # Phase 1 — health records, suspension, parity comparison
├── quickstart.md                  # Phase 1 — how to run and validate it
├── contracts/
│   ├── surface-parity.md          # What "equivalent" means, and how it is compared
│   ├── dependency-health.md       # Monitoring, refusal placement, the two denial classes
│   ├── suspension-and-sweep.md    # ADR-0049's lifecycle, and what replaces PARKED
│   └── conformance-mcp.md         # Rows in force, including the parity row finally claimed
├── checklists/requirements.md
└── tasks.md                       # /speckit-tasks output — not created here
```

### Source (repository root)

```text
src/surfaces/mcp/
├── server.py                      # The MCP service; a client of 008's core, as the caller
├── operations.py                  # The operation set, compared against the API's snapshot
└── health.py                      # Dependency reachability — the single owner of "healthy"

src/core/dependencies/             # Platform mechanism, not surface: runs consult it
├── types.py                       # DependencyHealth, HealthState (unknown == unhealthy)
├── store.py                       # Health records in Postgres, not memory
└── gate.py                        # The pre-execution refusal, INSIDE the hook pipeline

src/core/durability/
├── types.py                       # + SUSPENDED, naming a dependency; PARKED removed
├── resume.py                      # Suspension replaces parking
└── sweeper.py                     # Resumes suspended runs on recovery. No polling by runs

infra/jobs/
└── mcp.nomad.hcl                  # A `service` job — the first persistent one

.github/workflows/
├── ci.yml                         # Fast lane, unchanged, still fork-safe
└── enclave.yml                    # Second lane: non-fork PRs, runs `make conformance`

.specify/memory/constitution.md    # Amended: grant-expiry parking -> grant-expiry stop
docs/adr/0049-*.md                 # Proposed -> resolved
```

**Structure Decision**: The dependency mechanism lives in **`src/core/dependencies/`, not
under `src/surfaces/mcp/`**, and that placement is the main structural decision here. The
MCP service *hosts* the health checker because it is the thing that runs continuously, but
the refusal is consulted by every run regardless of which transport started it. Putting the
gate under the surface would mean a run started through the CLI ignoring a dependency the
platform knows is down — the same mistake as putting authorization in a transport.

Suspension belongs to `durability` because it is a run-lifecycle state, and it replaces
something that already lived there.

## Complexity Tracking

No Constitution Check violations. Three entries recorded because each is a real cost that a
reviewer should see stated rather than infer.

| Addition | Why needed | Simpler alternative rejected because |
|-----------|------------|-------------------------------------|
| A persistent operated component | ADR-0049's health checks and sweeper need something that outlives a run, and every other component ends when its work ends | A cron-style periodic batch job would avoid the persistent service, but the health checker needs to answer *on demand* — a run about to call a product asks now, not at the next tick. Recovery detection alone could be periodic; the refusal path cannot |
| Amending the parity row rather than claiming it | The row says "across all four transports" and there are two; claiming it would assert something untrue | Claiming it is the stub ADR-0047 forbids, in the feature whose spec refuses stubs. Deferring again leaves the gate inert until a fourth transport lands, so it never catches a two- or three-transport divergence — which is when divergence actually starts |
| Removing `RunState.PARKED` | ADR-0049 supersedes the re-consent rule that created it, and a state nothing can enter is worse than none | Leaving it as a deprecated no-op would keep a state in the sealed core that means nothing, and the constitution would still name a gate row for behaviour that no longer exists |
| A second CI workflow | Sixteen merge-blocking rows have no automated runner | Extending the fast lane would require exposing a licence secret to fork pull requests, which trades a coverage gap for a credential-disclosure one |
