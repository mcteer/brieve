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
| 005 | Durable execution | ADR-0024, ADR-0026, ADR-0048, ADR-0018 (consumes) | All seven durability rows |

## In progress

| # | Feature | ADRs | Status |
| --- | --- | --- | --- |
| 006 | Deployment module tree — the enclave, productized | ADR-0048, ADR-0025, ADR-0015, ADR-0007 | Spec drafted. `make dev-up` already shipped as tooling (#34); what remains is the parameterized tree and running the suite as a Nomad job |

> **A feature has no number until `/speckit-specify` creates its directory.** Refer to unstarted
> work by name. Guessing the next number reads as a fact, propagates into merged documents, and
> is wrong the moment anything is specified out of order.
>
> **Numbers are identifiers, not sequence.** 005 was assigned to durable execution before the
> local environment was understood to precede it — and then 005 shipped first anyway, because
> the blocking part of the environment turned out to be one Makefile target. The order of work
> here does not match numeric order and is not meant to. Renaming a merged spec directory would
> churn every reference to it for no gain.

### 006 — Deployment module tree

**Scope changed after 005 shipped, and the record should say so rather than read as though
the original plan held.** This was written as the feature that precedes durable execution and
makes `make dev-up` real. It did not: 005 landed first, and `make dev-up` was wired to the
existing `infra/dev-enclave` as tooling (#34) once it became the thing blocking implementation.

What that leaves is the part that was always the harder half — the **productized** tree.
`infra/dev-enclave` is labelled a proof and should not become the product front door by
inertia (ADR-0025).

Three specific gaps it closes:

1. **A parameterized tree** with the substrate as the only permitted delta, so the same
   configuration applies to a workstation and to customer infrastructure.
2. **Running the conformance suite as a Nomad job.** This is the honest gap in 005: the
   durability rows currently run on the host against a development Vault token, so the
   attestation path is proven *separately* by `jobs/harness-probe.nomad.hcl` rather than
   exercised *by the tests*. Closing it removes the only place a static token appears
   anywhere in the tree.
3. **What `make dev-up` still does not guarantee** — TLS from the control plane's own CA, HA,
   and an unseal shape that is not 1-of-1 with the key next to the server. All three are
   deliberately absent today and listed in `infra/dev-enclave/README.md`.

Replaces `fake_identity_fabric` as the thing guarantees are proven against. The fake remains a
test double for suites that are not about identity.

**In scope, and easy to lose:** revoking the bootstrap root token once Terraform has applied the
trust configuration. `infra/dev-enclave` deliberately retains it — that is what makes re-applying
convenient — and ADR-0015's flow requires that a deployment does not. A dev shape that silently
becomes the deployed one is the failure this entry exists to prevent.

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
| Durability scenarios (ADR-0024/0026) | 005 | ✅ In force — all seven, both providers. **Not run by CI**: the fast lane is fork-safe and cannot stand up a licensed Vault. See `specs/005-durable-execution/contracts/conformance-durability.md` |
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
