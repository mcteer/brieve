# ADR-0044: Authorization doctrine — two domains, entitlement mirroring, federate before broker

- **Status**: Accepted
- **Date**: 2026-07-24
- **Relates to**: [ADR-0015](0015-control-plane-vault-as-trust-fabric.md), [ADR-0016](0016-control-groups-gate-authority-changes.md), [ADR-0026](0026-delegation-grants-and-per-step-tokens.md), [ADR-0033](0033-four-transports-one-authorization-core.md)
- **Requirements**: R2, R3

## Context

"The agent acts with the user's authority" had been treated as a single statement. It is
two, and they are enforced in different places by different systems.

**Harness-domain authorization** is what a user may ask of the platform: which query
classes, which tenant scope, what data visibility. The platform decides this entirely, from
identity-provider claims, through the scope algebra.

**Product-domain authorization** is what happens when the agent acts in a managed product.
The platform does not own that decision — the product does, according to its own
permissions model.

Conflating them produces a specific and dangerous gap: an agent that passes every harness
check and then acts in a product with *more* authority than the requesting human has there.

That gap widens because products differ in what they can validate. Some accept externally
issued identity tokens and can evaluate them directly. Others cannot validate foreign
identity and only accept their own credentials — which means acting on a user's behalf
requires wielding a credential that is not scoped to that user. That is a textbook confused
deputy: the platform holds authority the requester does not, and something must ensure it is
not exercised beyond them.

There is also a policy-jurisdiction question. Several engines can express similar rules, and
rules duplicated across engines drift — with the drift discovered when one denies what
another permits.

## Decision

**Two authorization domains, both checked, independently.**

- **Harness domain** — entitlements decided by the platform from identity-provider claims
  via the scope algebra.
- **Product domain** — **entitlement-mirrored**: the agent acts with **the same authority as
  the requesting user — no amplification, no arbitrary reduction** — and both checks must
  agree.

**Credential translation follows one rule: federate where the product can validate external
identity; broker only where it cannot.**

- **Federate** — the product's own trust of the control plane as an identity issuer, and
  cloud workload identity federation. **Zero standing credentials in either direction**,
  with claim mapping owner-administered.
- **Broker** — only where federation is impossible: a secrets engine on the control plane
  minting **fresh, leased, per-request credentials**, with layered policy on issuance. Its
  management token is **the platform's single standing credential**, rotated and
  quorum-governed.

**Confused-deputy compensating control**: where a brokered credential is coarser than the
individual user, a **pre-tool-use check resolves the user's own effective product
entitlements and enforces them** before the credential is wielded. A user with narrower
permissions than their team cannot use a team-grain credential to exceed themselves.

**Policy jurisdictions are disjoint**: one engine decides, another enforces credential
issuance, a third enforces change content. **No rule is duplicated across engines.**

Governed mappings sit behind multi-party approval
([ADR-0016](0016-control-groups-gate-authority-changes.md)), with drift reconciliation on
the recurring review cadence.

## Consequences

The claim "the agent cannot exceed the human" becomes true in the product as well as in the
platform, which is where it actually matters. Mirroring is also a stronger and more precise
statement than scoping: no amplification *and* no arbitrary reduction, with two independent
checks that must agree.

Federating wherever possible keeps the zero-standing-credential posture intact almost
everywhere, and naming the single exception makes it auditable as a count — one, rotated,
quorum-governed. A second standing credential would be a constitutional event rather than a
configuration change.

The confused-deputy pre-check is the part that will be tempting to skip, because it costs a
round trip on every brokered action and its benefit is invisible when it passes. Its
conformance case — a team member with narrower permissions than their team must be denied
what the team credential would allow — exists precisely because the failure is silent.

Disjoint jurisdictions prevent duplicated-rule drift, at the cost of requiring people to
know which engine owns which class of rule. That is a documentation and enablement
obligation, not a design flaw.

The remaining costs are integration-shaped: broker paths need lease lifecycle management and
revocation verified against live systems, and governed mappings can drift from what a
product's own console shows, which is why drift reconciliation is scheduled rather than
assumed.
