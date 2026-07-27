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
| 006 | Deployment module tree | ADR-0025, ADR-0048, ADR-0015, ADR-0007 | — (infrastructure; the durability rows now run under an attested identity) |
| 007 | Control Groups | ADR-0016, ADR-0015, ADR-0048 | — (no new blocking row; component tests against the real Vault) |

## In progress

Nothing. The next feature is the top of [Next](#next) — the northbound **API**, first of the
four transports, and the one the other three consume.

> **A feature has no number until `/speckit-specify` creates its directory.** Refer to unstarted
> work by name. Guessing the next number reads as a fact, propagates into merged documents, and
> is wrong the moment anything is specified out of order.
>
> **Numbers are identifiers, not sequence.** 005 was assigned to durable execution before the
> local environment was understood to precede it — and then 005 shipped first anyway, because
> the blocking part of the environment turned out to be one Makefile target. The order of work
> here does not match numeric order and is not meant to. Renaming a merged spec directory would
> churn every reference to it for no gain.

## Next

Ordered by dependency first, then by which owed gate row it closes. Each entry names what it
unblocks — that is the argument for its position, and the thing to challenge if you disagree.

### Northbound surfaces — split into four (ADR-0033, ADR-0034, ADR-0035)

**One feature per transport, not one feature for four.** ADR-0033 requires all four to yield the
same verdict and equivalent audit events, and that parity is asserted *between* them — but
building four surfaces in one pass means getting parity right across four things that are all
still moving. Splitting lets each land against a settled core.

**The API goes first**, because the other three consume it rather than reimplementing the
authorization path. A CLI that talks to the core directly is a second authorization path
wearing a different name.

| # | Transport | Notes |
| --- | --- | --- |
| 008 | **API** | The surface the others consume. Carries the audit plane as a governed read path |
| — | MCP | The persistent service coding IDEs talk to. **Scope includes** the dependency health checks and the resume sweeper decided in ADR-0049 — both need a long-lived home, and this is it |
| — | CLI | Over the API |
| — | Portal | Over the API |

**Owed gate row:** four-transport surface parity. It stays owed until at least two transports
exist — parity cannot be asserted against a single surface, and a row claiming otherwise would
be a stub.

**Why here:** the first features that ship something a user touches directly. They need the
authorization core (002/003) and the approval gate (007) settled behind them; attempting them
earlier means building transports over guarantees still in motion.

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
| Durability scenarios (ADR-0024/0026) | 005 | ✅ In force — all seven, both providers, under an attested identity. **Not run by CI** (the fork-safe lane cannot hold a licensed Vault); the agent harness runs them before merge per `AGENTS.md`, and refuses the merge if the enclave cannot come up |
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
