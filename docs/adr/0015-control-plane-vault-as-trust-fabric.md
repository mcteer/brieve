# ADR-0015: A dedicated control-plane Vault is the agent registry and trust fabric

- **Status**: Accepted
- **Date**: 2026-03-18
- **Supersedes**: the CRD-based registry as identity system of record
- **Relates to**: [ADR-0016](0016-control-groups-gate-authority-changes.md), [ADR-0025](0025-enclave-is-the-default-topology.md), [ADR-0026](0026-delegation-grants-and-per-step-tokens.md), [ADR-0044](0044-authz-doctrine-and-credential-translation.md)
- **Requirements**: R1, R2, R3

## Context

Agent identity needs a system of record: something that knows which agents exist, what
each is permitted to become, and can mint short-lived credentials scoped accordingly.
The initial design used custom resources in the orchestrator as that record, which is
convenient — it is already there, it is declarative, and it fits the deployment model.

It is also wrong for this purpose, for a reason that only becomes clear when the threat
model is stated precisely. The agents this platform governs operate infrastructure. An
agent that could modify its own definition, raise its own ceiling, or register a new
instance would be able to escalate arbitrarily — and an orchestrator's resource store is
reachable by workloads running in that orchestrator. Making the identity record a
resource in the same substrate the agents run in means the containment boundary depends
on access control within that substrate holding perfectly, forever.

The requirements are also more specific than a resource store can satisfy: unique
attested identity per instance, registration enforced such that unregistered workloads
obtain nothing, ceiling policies that no task scope can exceed, and token exchange that
narrows authority per task. That is an identity system's job.

## Decision

**A dedicated control-plane Vault instance — provisioned by the installer's own
Terraform, before any agent exists — is the agent registry and trust fabric.**

It holds agent identities and registration, compiled ceiling policies, and acts as an
OAuth resource server supporting token exchange with rich authorization requests. It is
**human and CI managed only**, and sits **structurally outside every agent ceiling**: no
agent the platform governs can reach it, by construction rather than by policy. It runs
the hardest security posture in the deployment.

**The workload Vault is a different thing entirely** — an ordinary managed product
target, governed like Terraform or any other estate component. Conflating the two would
reintroduce exactly the escalation path this decision closes.

The division of labor is: **definitions in HCL** (design-time, version-controlled,
reviewed), **enforcement in Vault** (compiled ceilings, credential issuance),
**deployment via the operator** (the orchestrator remains the deployment mechanism, no
longer the identity record).

Fallbacks exist for organizations that cannot run a dedicated instance — a namespace on
an existing cluster, or a reduced CRD-only mode — with the assurance difference stated
rather than implied.

## Consequences

The escalation path is closed structurally. An agent cannot modify its own authority
because it cannot reach the system that defines it, which is a stronger claim than any
access-control configuration can make, and it is the claim regulated adopters actually
ask for.

It also gives the platform a real identity system rather than an improvised one:
short-TTL credentials, registration enforcement, ceiling policies, and standards-based
token exchange are features rather than things to build. This is adopt-first applied to
the hardest part of the architecture.

The costs are substantial and worth stating plainly. The platform now depends on a
dedicated, hardened instance of a specific product, with its own operational lifecycle —
unsealing, upgrades, backup, disaster recovery — owned by the same installer that
creates it. It is a blocking dependency: when it is down, task starts stop, by design.
And it is an enterprise-licensed component, which is a procurement conversation for every
adopter and a packaging question for distribution.

The day-zero ceremony that stands it up before any agent exists is unusual, and it is
deliberate: the trust fabric must exist before the things it governs, and a human-reviewed
plan-and-apply is the correct root-of-trust establishment for a system whose entire claim
is that agents never govern themselves.
