# ADR-0048: Nomad is the agent execution substrate, and its workload identity is the attestation

- **Status**: Accepted
- **Date**: 2026-07-25
- **Relates to**: [ADR-0015](0015-control-plane-vault-as-trust-fabric.md), [ADR-0025](0025-enclave-is-the-default-topology.md), [ADR-0026](0026-delegation-grants-and-per-step-tokens.md), [ADR-0007](0007-lean-and-federated-profiles.md), [ADR-0046](0046-multi-tenancy.md)
- **Requirements**: R2, R3, R12

## Context

[ADR-0025](0025-enclave-is-the-default-topology.md) defines the enclave as "an isolated,
self-scaffolded cluster — a standalone orchestrator, the control-plane Vault, and Postgres."
It never says which orchestrator. That was reasonable while nothing depended on the answer,
and it stopped being reasonable the moment two things did.

The first is isolation. An agent executes model-chosen tool calls against infrastructure. The
harness enforces what those calls may do, but enforcement inside a process is not a containment
boundary — something has to bound what the process itself can reach. The harness needs to run
*inside* something.

The second is attestation, and it is the sharper one. Principle IV manufactures authority per
task from an **attested workload identity** exchanged at the control-plane Vault. That phrasing
assumes an attester exists — some component that can assert "this workload is what it claims to
be" in a way Vault will accept. Nothing in the record said what produces that assertion. Without
naming it, "attested workload identity" is an aspiration, and every implementation is free to
substitute something weaker while appearing to satisfy the principle.

Leaving the orchestrator unnamed had a second cost that only became visible in practice: because
no component was named, development substituted a fake identity fabric and treated the real one
as future work. That is a reasonable seam for an external dependency and the wrong posture for a
component the project itself deploys.

## Decision

**Nomad is the orchestrator ADR-0025 leaves unnamed, and the agent harness runs sandboxed inside
a container Nomad schedules.** The container is the containment boundary; the harness inside it
is the enforcement boundary. They are different mechanisms and both are required.

**Nomad workload identity is the attestation.** A scheduled allocation receives an identity from
Nomad, presents it to the control-plane Vault, and Vault performs RFC 8693 token exchange with
rich authorization requests against ceiling policies. This is the concrete form of Principle IV's
`attested workload identity → control-plane Vault → RFC 8693 + RAR` chain. No other path to
per-task authority is supported.

**Nomad schedules the enclave's supporting components**, Postgres among them — the same
scheduling substrate in development and in production, so what is exercised locally is what runs
for real.

**Nomad does not schedule the control-plane Vault.** [ADR-0015](0015-control-plane-vault-as-trust-fabric.md)
is explicit that making the identity record a resource in the substrate the agents run in "means
the containment boundary depends on access control within that substrate holding perfectly,
forever." Vault is provisioned by the installer's own Terraform before any agent exists, and sits
outside the substrate deliberately. Scheduling it under Nomad would make the trust fabric depend
on the thing it exists to constrain.

The bootstrap order follows from that and is not arbitrary: **Terraform → Vault → Nomad →
harness**. Each link is established before the one that depends on it.

**Local development runs the same chain.** The enclave in miniature, on a workstation, is not a
convenience approximation — it is the same components in the same order. Substituting a lighter
scheduler locally would mean the attestation path, which is the whole basis of per-task
authority, is never exercised until production.

## Consequences

The largest consequence is that a guarantee we had been treating as harness discipline turns out
to be structural. [ADR-0026](0026-delegation-grants-and-per-step-tokens.md) requires that resume
re-authenticates and never replays a token. Under this decision a resumed run is a *new
allocation with a new workload identity* — the previous allocation's identity no longer exists,
so replay is not prevented by careful coding, it is unavailable. Single-writer fencing lands the
same way: a partitioned zombie is presenting a superseded identity, and rejecting it is an
identity check rather than a race. Code still has to be written, but it is enforcing a property
the substrate already makes true, which is a much better place to stand.

Naming the orchestrator also converts the identity fabric from a permanent fake into a real
component with a test double. Development against the real attestation path costs setup time and
buys the only thing that matters here: the per-task authority chain is exercised, not simulated.

The costs are real and worth stating plainly. Nomad becomes a hard dependency of both the product
and the development environment — a contributor cannot meaningfully work on identity, durability,
or execution without it running. That is an operated component in the enclave baseline, which
Principle VI permits only for a named reason; the reason is that Principle IV's attestation
requirement has no other supplier, and a scheduler was already implied by ADR-0025's "standalone
orchestrator." This ADR names it rather than adding it.

Binding to a specific scheduler also creates coupling ADR-0025 anticipated but did not have to
confront: Kubernetes remains supported as an accommodation, and it must now supply an equivalent
attested workload identity that Vault will accept. The anti-fragmentation rule holds — identical
core, control-plane posture, packs, and conformance suite, with the substrate as the only
permitted delta — but "substrate delta" now includes the attestation mechanism, which is a more
consequential difference than a scheduling difference. Any Kubernetes path must demonstrate the
same conformance assertions rather than an analogous story.

Finally, this makes local setup heavier than a Python project's contributors would expect:
Terraform, Vault, Nomad, and Docker before the first test that touches identity or durability. The
mitigation is to make standing it up a single documented command rather than to make the stack
optional — an optional real stack becomes an unused one.

## Notes

Recorded after the fact. The decision was in effect — Nomad, Vault Enterprise, and Docker were
already the working environment — but appeared in no ADR, so specs 002 through 004 were written
against a fake identity fabric described as "production IdP/Vault fabric remains later." That
framing was a consequence of the gap, not a deliberate deferral.

The seam those specs built against holds: `IdentityFabric` is a protocol, and a Vault-backed
implementation satisfies it exactly as the fake does. What changes is which implementation the
guarantees are proven against.
