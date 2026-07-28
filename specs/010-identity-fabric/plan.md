# Implementation Plan: Production Identity Fabric

**Branch**: `spec/010-identity-fabric` | **Date**: 2026-07-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/010-identity-fabric/spec.md`

## Summary

Replace `FakeIdentityFabric` as the source of authority for every governed run. Agent
ceilings and role-to-scope bindings move into the control-plane trust fabric, read at
runtime by a production implementation that authenticates with an attested workload
identity; the product-entitlement seam becomes real while the products behind it stay faked.

The approach follows from Phase 0, which was conducted against the running enclave rather
than the source tree — and which changed the plan twice. Registrations turned out to be
readable, so the feature is possible as specified. The registry's schema turned out to be
closed, so the clarified "first-class registry field" becomes a dedicated record in the same
trust fabric rather than a field on the registration. See [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: No new runtime dependencies. Vault's HTTP API is reached with
`urllib` through the same shape `VaultDatabaseCredentials` already uses — adding an HTTP
client to the core install for four GETs would fail Principle VI.

**Storage**: Control-plane Vault (registry, ceiling records, role bindings). Postgres is
untouched by this feature.

**Testing**: pytest. Unit and component rows hermetic; the enclave rows run inside a Nomad
allocation under an attested identity, as 005/008/009 do.

**Target Platform**: Linux containers under Nomad; macOS and Linux for development.

**Project Type**: Governed runtime library plus infrastructure module tree.

**Performance Goals**: Identity resolution adds network reads to run start and to each step
(FR-008 forbids caching policy). Budget: resolution must fail closed within a bounded wait
(FR-018) rather than hang. No throughput target — this path is per-step, not per-request.

**Constraints**: Fail closed on every resolution failure. No static credential anywhere. The
trust fabric must not be reachable from any agent-governed tool (FR-016).

**Scale/Scope**: Tens of agent definitions per deployment; the registry is human- and
CI-managed and low-frequency by design (ADR-0015).

### What this feature changes that is not its own

**Sealed core** (Principle V — requires approved spec and security-maintainer review, both
of which this feature has):

- `src/core/authority/fabric.py` — the protocol loses its two test-only methods (FR-013).
- `src/core/authority/` gains a production implementation package.
- `src/core/run.py` and the resume path — a mid-run resolution failure must suspend naming
  the trust fabric (FR-008a), reusing 009's suspension rather than adding a second path.

**Infrastructure**:

- `infra/modules/trust-fabric/` — a ceiling record store, role bindings, a read policy, and
  a role for whoever reads them.
- `infra/environments/*/variables.tf` — agent definitions gain a harness-domain ceiling.

**Test harness**: `tests/harness/dispatched_run.py` lives under `tests/` because a production
entrypoint had no fabric to resolve through (FR-015). That reason expires here.

### The seams this feature consumes, and whether they already accept what it needs

009 recorded eight instances of "a mechanism specified without the thing it acts through",
and the check it produced applies directly: **when a task says "wire A to B", verify A's
interface accepts what B requires.** Checked in advance this time, which is the point.

| Seam | Built by | Accepts what this feature needs? |
| --- | --- | --- |
| `IdentityFabric` protocol | 002 | **No** — two methods are test-only (FR-013). Changing it is in scope |
| `AuthorityScope` | 002 | Yes — `tool_names` + `product_actions`, frozen, with `intersect` / `issubset` |
| `FabricFault(reason_code=)` | 002 | Yes — reason codes already reach refusals |
| `VaultDatabaseCredentials` | 005 | **Partly** — it logs in and reads exactly one creds path. The fabric must read several unrelated paths under the same identity |
| `suspend_run(run, *, awaiting=)` | 009 | Yes — `awaiting` is a free string, so `"trust-fabric"` needs no change |
| `Sweeper` / `awaited_products()` | 009 | Yes — the sweeper iterates whatever the index says runs wait on |
| `PostgresDependencyStore.state_of` | 009 | Yes — but see the circularity below; the fabric sits *underneath* this |
| Control Groups approval | 007 | Yes — consumed unchanged for mapping changes |

**The one needing care** is the 005 credential seam. Extending it is a sealed-core change;
the alternative — a second class that authenticates its own way — would be a second
authentication path to the trust fabric, which is the shape Principle II forbids for tools
and is no more attractive here.

### The circularity this feature introduces, stated before it is discovered

Spec FR-008b names it and the plan must hold it: **the trust fabric is a dependency of the
mechanism that monitors dependencies.** 009's health checker and sweeper reach Postgres with
credentials the fabric issues, so while the fabric is down they are degraded too — and the
component that would notice its recovery depends on the thing recovering.

It terminates, and only in one order:

```
fabric returns
  → the checker's login succeeds
  → the checker obtains database credentials
  → the checker records trust-fabric healthy
  → the sweeper resumes runs suspended on it
```

Nothing else in this platform has this property, and no existing row asserts an ordering
constraint of this kind. It is a deliverable, not a note.

## Constitution Check

*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md) (v1.2.0).*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | Consumes Vault's registry engine and identity store; builds no registry product. The ceiling record is our concept in their store, which is the glue direction |
| II — Total Interception; One Governed Tool Layer | **Pass** | No second authorization path. The entitlement check is a pre-tool-use hook on the existing pipeline, not beside it |
| III — Fail-Closed, In-Process Enforcement | **Pass** | Every resolution failure refuses (FR-003, FR-007, FR-008, FR-011, FR-018). Unknown is never empty and never full |
| IV — Zero Standing Credentials; Authority Per Task | **Pass, with a recorded divergence** | No static credential added; the fabric authenticates by attested identity. **But** Principle IV describes manufacture as "RFC 8693 + RAR against ceiling policies" and the implementation is a JWT role login (research Finding 5). This feature neither introduces nor closes that gap; it records it |
| V — Sealed Core, Versioned Seams | **Pass** | `src/core/authority/` changes carry an approved spec plus security-maintainer review. The protocol change is a narrowing and every caller is in-repo |
| VI — Lean by Default | **Pass** | No new runtime dependency; a handful of HTTP reads through the existing `urllib` shape |
| VII — Anti-Fragmentation | **Pass** | Ceiling records and role bindings live in the substrate-independent part of the tree; no substrate delta |
| VIII — Eval-Gated Promotion | **N/A** | No models, packs, or prompts |
| IX — Evidence Over Claims | **Pass** | Resolution refusals are audited with distinguishing reason codes (FR-012); enclave rows run against the real fabric, not a recorded response (FR-017) |
| X — The Decision Record Governs | **Pass, and the reason for two deliverables** | FR-020 requires an ADR for what the registry now holds; Finding 5's divergence is recorded rather than absorbed |

**Gate result**: **PASS — proceed to Phase 0.**

### Who runs the blocking rows

This feature adds enclave-dependent rows. Per constitution v1.2.0 and the lane 009 shipped:
**the enclave CI lane runs them on same-repo pull requests**, and **the agent harness in the
IDE runs them for fork pull requests and whenever the lane could not run**. The conformance
contract records this, per the Quality Gates requirement.

### Post-design Constitution Check

Re-evaluated after Phase 1. Two entries changed, and both are worth naming.

**Principle I moved from an easy Pass to a considered one.** Phase 1 puts the ceiling record
in KV, and `registry.tf` opens with "a first-class registry, **not a convention implemented
over kv**." What resolves it: that comment rejects reimplementing *Vault's* concept over KV
when Vault ships the engine. The harness-domain ceiling is *our* concept, for which no engine
exists. Storing our data in their store is glue; rebuilding their product would not be.

**Principle IV's divergence is load-bearing enough to restate.** The verdict stays Pass — the
feature neither introduces nor worsens the gap, and the ceiling it reads is genuinely
enforced. But nobody should finish this plan believing authority manufacture matches the
constitution's description. It does not. [research.md](research.md) Finding 5 is the record.

**Gate result after design**: **PASS.**

## Project Structure

### Documentation (this feature)

```text
specs/010-identity-fabric/
├── spec.md
├── plan.md              # This file
├── research.md          # Phase 0 — five findings from the live enclave
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── identity-fabric.md       # The protocol, after the test-only methods leave
│   ├── ceiling-record.md        # What the trust fabric holds, and who may read it
│   └── conformance-identity.md  # The rows, and who runs them
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 — NOT created by /speckit-plan
```

### Source (repository root)

```text
src/core/authority/
├── fabric.py                 # CHANGED — protocol drops issue/get_brokered_material
├── vault_fabric.py           # NEW — the production implementation
├── ceiling.py                # NEW — reading and validating a ceiling record
└── entitlements.py           # NEW — the product-entitlement seam (interface)

src/core/durability/
└── credentials.py            # CHANGED — a general authenticated read, not one creds path

src/core/
├── run.py                    # CHANGED — the fabric a run resolves through
└── durability/resume.py      # CHANGED — suspend naming the trust fabric

infra/modules/trust-fabric/
├── ceilings.tf               # NEW — harness-domain ceiling records + role bindings
├── policies.tf               # CHANGED — a narrow read policy for the fabric
├── auth.tf                   # CHANGED — the reader role
└── variables.tf              # CHANGED — definitions carry a harness ceiling

infra/environments/*/variables.tf   # CHANGED — a definition whose ceiling resolves

tests/
├── unit/                     # protocol shape, reason codes, no src → tests imports
├── component/                # resolution behaviour against a fake transport
└── conformance/identity/     # enclave rows against the real trust fabric

docs/adr/
└── 00NN-harness-ceilings-live-in-the-trust-fabric.md    # NEW — FR-020
```

**Structure Decision**: The production fabric lives in `src/core/authority/` beside the
protocol it implements, not in a provider package. It is not an extension point — there is
one trust fabric per deployment and ADR-0015 names it — and putting it behind a provider seam
would advertise a choice the architecture does not offer.

## Phases

**Phase 0 — Research.** Complete: [research.md](research.md).

**Phase 1 — Design & contracts.** Complete: [data-model.md](data-model.md),
[contracts/](contracts/), [quickstart.md](quickstart.md).

**Phase 2 — Tasks.** `/speckit-tasks`. Not created here.

### Sequencing notes for whoever writes tasks

The user stories are independently testable, but two orderings are not free:

1. **The protocol narrowing (US5) goes first, not last.** It is a sealed-core change that
   every other story's code sits on; doing it after three implementations exist means
   changing three implementations.
2. **The enclave fixture (research D4) precedes every enclave row.** `demo-agent`'s ceiling
   grants a path under a mount that is not mounted, so rows written against it would pass
   whether enforcement worked or not.

Everything else follows spec priority: ceilings, then user scope, then policy, then
entitlements.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| Ceiling records in KV rather than on the registration | The `agent_registry` engine has a closed schema (research Finding 3); there is no field to add | Encoding the ceiling in a Vault policy produces paths that address nothing and are parsed only by us — rejected at clarify. RAR is the constitutional end-state and its own feature (Finding 5) |
| Extending a 005 sealed-core credential seam | The fabric reads several Vault paths under the same attested identity; the existing class reads exactly one | A second authentication class would be a second path to the trust fabric — the shape Principle II forbids elsewhere, for the same reason |
