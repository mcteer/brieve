# Roadmap

What ships in what order, and why that order. Derived from the decision record
([`docs/adr/`](docs/adr/)) and the constitution's Quality Gates — not a separate plan.

**This file is guidance, not governance.** Where it conflicts with an Accepted ADR or the
constitution, those win and this file is corrected. Its job is to stop feature sequencing from
being re-derived at the start of every spec.

## How to use it

- **Starting a feature?** Take the top of [Next](#next). If you take something else, say why in
  the spec's Assumptions.
- **Deferring something in a spec?** Every "out of scope" line is a promise. Add it here, or to
  [Demand-driven](#demand-driven--trigger-gated) if it should never be scheduled by default.
- **Landing a feature?** Move it to [Shipped](#shipped), and move any Quality Gate row it
  attached out of [Owed gate rows](#owed-quality-gate-rows). ADR-0047 makes those rows binding
  the moment their feature exists.

## Shipped

| # | Feature | ADRs realized | Gate rows attached |
| --- | --- | --- | --- |
| 001 | Dev toolchain | ADR-0007, ADR-0028 | — |
| 002 | Governed core | ADR-0006, ADR-0009, ADR-0020, ADR-0037 | — |
| 003 | Per-task authority | ADR-0015, ADR-0026 (partial), ADR-0042, ADR-0044 | — |
| 004 | Primary adapter | ADR-0001, ADR-0017, ADR-0019, ADR-0047 | Governance-ordering, fail-closed, governed entry |

## In progress

| # | Feature | ADRs | Status |
| --- | --- | --- | --- |
| 006 | Local environment — the enclave in miniature | ADR-0048, ADR-0025, ADR-0015, ADR-0007 | Next to spec — **lands first** |
| 005 | Durable execution | ADR-0024, ADR-0026, ADR-0018 (consumes) | Spec merged (#27); **needs correction**; lands second |

> **Spec numbers are identifiers, not sequence.** They are assigned when `/speckit-specify`
> runs, so 005 was taken by durable execution before the local environment was understood to
> precede it. The order below is the order of work; the numbers are just names. Renaming a
> merged spec directory would churn every reference to it for no gain.

### 006 — Local environment

Stands up the enclave on a workstation, in the order the trust chain requires:
**Terraform → Vault → Nomad → harness**. Makes `make dev-up` real, the way 004 made
`make conformance` real — the command has been a reserved exit-2 stub since 001, documented
as "local stack: dev-mode identity fabric, Postgres, collector, harness."

Why it precedes durable execution: 005's central guarantee — resume re-authenticates, never
replays — is a property of Nomad workload identity rather than harness discipline (ADR-0048).
Proving it against a fake identity fabric proves the harness calls the fabric correctly, which
is a weaker claim than the one the spec makes. Postgres is likewise a real stack component;
substituting something lighter would mean the durability code ships untested against what it
actually runs on.

Replaces `fake_identity_fabric` as the thing guarantees are proven against. The fake remains a
test double for suites that are not about identity.

### 005 — Durable execution

Attaches the durability Quality Gate row: kill/resume, re-observe-never-re-execute,
re-auth-never-replay, double-resume fencing, grant-expiry parking, duplicate-side-effect
rejection, drain-across-upgrade.

**The merged spec (#27) assumes a hermetic reference provider and defers Postgres.** That
assumption is now wrong — see ADR-0048 and the local-environment entry above. Correct it via
`/speckit-clarify` before planning: real Postgres scheduled by Nomad, and real Vault for the
re-authentication path.

## Next

Ordered by dependency first, then by which owed gate row it closes. Each entry names what it
unblocks — that is the argument for its position, and the thing to challenge if you disagree.

### 007 — Control Groups (ADR-0016)

Quorum-gated authority changes: who may widen a scope, restore revoked access, or change IdP
claim-to-role mapping.

**Why here:** 004 left the approval hook as a deny-by-default stub, and 005 parks runs awaiting
consent that nothing can currently grant. Both are honest interim states, but they compound —
each additional feature that parks or requires approval widens a gap with no surface behind it.
This is also the first feature whose subject is *humans authorizing*, which every
approval-shaped thing downstream depends on.

**Unblocks:** real human-in-the-loop approvals; 005's parked-run resolution; ADR-0016's
restoration quorum.

### 008 — Northbound surfaces (ADR-0033, ADR-0034, ADR-0035)

Four transports — MCP, API, CLI, portal — over one authorization core, with surface parity
conformance-asserted: the same operation yields the same verdict and equivalent audit events on
every transport. Includes the audit plane as a governed read path.

**Why here:** the first feature that ships something a user touches directly, and it needs the
authorization core (002/003) plus an approval surface (007) to be behind it. Attempting it
earlier means building transports over guarantees that are still moving.

**Owed gate row:** four-transport surface parity.

### 009 — Capability packs and eval gates (ADR-0004, ADR-0022, ADR-0030, ADR-0031, ADR-0039, ADR-0045)

Packs, prompts, and skills as pinned, eval-gated artifacts; the Qualified Model Matrix; per-role
model bindings; competency tiers.

**Why here:** brings Principle VIII online, which no feature has needed yet — the eval-gate
machinery does not exist. It depends on nothing in 007/008 strictly, so it can move earlier if
content work becomes the priority; it sits here because a pack with no surface to invoke it and
no approval path is hard to evaluate end to end.

**Owed gate rows:** all Eval gates (must-deny safety, must-decline scope, citation accuracy,
estate-state fixtures, report fidelity).

### 010 — Deferred disclosure and code mode (ADR-0040, ADR-0041)

Productizes deferred tool/capability disclosure, and ships code mode — but only with verified
per-call hook parity, which ADR-0041 makes an unconditional gate rather than a default.

**Why here:** both are efficiency features gated on proving governance survives them. Neither is
worth doing before there is enough tool surface for the efficiency to matter.

**Owed gate row:** tool-call parity under deferred disclosure.

### 011 — Multi-tenancy (ADR-0046)

One platform, isolated tenants, using the products' own isolation primitives.

**Why last of the scheduled set:** it multiplies every guarantee above it. Isolating tenants
before the things being isolated are stable means doing the work twice.

## Demand-driven / trigger-gated

Deliberately unscheduled. Each needs a recorded trigger before it enters [Next](#next) — that is
the decision, not an omission.

| Item | ADR | Trigger |
| --- | --- | --- |
| Second framework adapter (LangGraph) | ADR-0017 | Demand. The ADR makes it explicitly demand-driven; 004's FR-014 forbids shipping it speculatively |
| Dedicated workflow-engine durability provider | ADR-0024, ADR-0028 | A named trigger: scale, an existing deployment, or a requirement the library provider cannot meet |
| Wire-level guardrail (second protection layer) | ADR-0014 | Optional by design; in-process hooks are the primary layer |
| Retrieval | ADR-0029 | Runs in the Postgres a deployment already has — needs that Postgres to exist first |
| Vertical policy/content profiles | ADR-0003 | Horizontal first. Profiles ship as policy and content, not as forks |

## Owed Quality Gate rows

The constitution names these as blocking for adapters and providers. Under ADR-0047 each binds
when its feature lands, and until then must be **absent or an explicit skip citing its deferring
ADR — never a passing stub.**

| Row | Attaches with | Status |
| --- | --- | --- |
| Governance-ordering, fail-closed, governed entry | 004 | ✅ In force |
| Durability scenarios (ADR-0024/0026) | 005 | Planned |
| Four-transport surface parity | 008 | Deferred — ADR-0033 |
| Tool-call parity under deferred disclosure | 010 | Deferred — ADR-0040 |
| Eval gates (packs, models, policies) | 009 | Deferred — Principle VIII |
| Registry isolation (control-plane write denials) | — | **Unassigned** — see gaps below |

## Open records

Two ADRs remain **Proposed** and are expected to resolve rather than linger. Neither blocks the
sequence above, but a Proposed record that quietly becomes permanent is a failure of the process
([`docs/adr/README.md`](docs/adr/README.md)).

- **ADR-0011** — harness-first SDKs at the perimeter; awaiting the evidence ADR-0012 produces.
- **ADR-0012** — harness-as-runtime vs governance-attach; an experiment with a defined decision
  point, partially amended by ADR-0027.

## Known gaps in the record

Found while deriving this file. None blocks work; all three make the record harder to reason
from, and each is worth its own small change.

1. **R1–R17 are referenced but never defined in-repo.** The constitution requires every spec to
   declare which mandated requirements it touches, and the spec template enforces it — but no
   file enumerates them. Every spec to date has cited them from context. They should be written
   down.
2. **The architecture document the constitution cites is not in this repository.** The
   constitution says it is "sourced from architecture v1.14"; that document lives elsewhere.
   Anything it contains that governs — including sequencing — is currently unavailable to anyone
   working only from the repo, which is what made this file necessary.
3. **The registry-isolation gate row has no owning feature.** It is named in the constitution's
   Quality Gates but no ADR defers it and no planned feature attaches it. Noted in 004's
   conformance contract as deriving from Principle IV and ADR-0025 rather than from a deferral.
   Either a feature should claim it or ADR-0047 should distinguish *deferred by decision* from
   *not yet applicable*.

## Maintaining this file

Update it in the same change that lands a feature or defers work — not afterwards. A deferral
recorded only in a spec's "out of scope" list is invisible to whoever plans the next feature,
which is the failure this file exists to prevent.
