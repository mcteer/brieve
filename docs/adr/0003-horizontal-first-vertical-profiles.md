# ADR-0003: Build horizontal; verticals ship as policy and content profiles

- **Status**: Accepted
- **Date**: 2026-01-15
- **Relates to**: [ADR-0007](0007-lean-and-federated-profiles.md)
- **Requirements**: R9

## Context

The platform targets organizations in financial services, healthcare, retail, and the
public sector. Each brings its own regulatory frame — SOX and DORA, HIPAA, PCI-DSS,
NIST 800-53 — with different evidence expectations, retention rules, data-handling
constraints, and identity requirements.

Two obvious approaches both fail. Building a general platform and telling regulated
adopters to figure out compliance themselves puts the hardest work on the people least
equipped to do it, and produces a different interpretation at every site. Building
vertical editions — a healthcare product, a public-sector product — forks the codebase
along regulatory lines, which multiplies maintenance, guarantees drift between
editions, and means a fix in one vertical may or may not reach the others.

The insight that resolves it: the regulatory differences are almost entirely in
*policy and content*, not in *mechanism*. Every vertical needs identity bootstrap,
token exchange, delegation chains, a hook pipeline, risk classes, an audit schema, a
redaction engine, and an installer. What differs is which policy bundle is loaded,
which retention period applies, which evidence template a report renders into, which
models are approved, and which deployment constraints apply.

## Decision

**Build horizontally. A vertical is a profile, not a product.**

The horizontal platform — identity and trust, policy engine and hook pipeline, audit
schema and store, data handling, packaging, model gateway abstraction — is built once
and is identical everywhere.

A vertical ships as a **Vertical Profile**: a policy bundle, evidence templates, and a
deployment/model profile. **Zero core code.** If serving a vertical requires changing
core, that is a signal the horizontal mechanism is incomplete — the fix belongs in
core, generalized, not in a vertical branch.

The Baseline Governance Profile (NIST 800-53 / ISO 27001) is built first and serves as
the proof that the profile mechanism works. Industry-specific profiles follow through
the same pipeline, on demand rather than speculatively.

## Consequences

One codebase serves every vertical, so a fix or improvement reaches all of them
simultaneously and cannot silently apply to one and not another. Adding a vertical
becomes content work — authoring a policy bundle and evidence templates — rather than
engineering work, which means it can be done by people with regulatory expertise rather
than platform expertise, and can be done by adopters themselves.

The constraint cuts both ways, and that is deliberate: a vertical requirement that
genuinely cannot be expressed as policy and content forces a real design conversation
about the horizontal mechanism, rather than being absorbed as a special case. That
conversation is slower in the moment and correct in aggregate.

The cost is that the horizontal mechanism must be general enough to express regulatory
requirements it was not specifically designed for, and generality is harder to build
than specificity. Some vertical requirements will fit awkwardly at first. The rule
holds anyway: the fix is a more general mechanism, not a vertical fork.

Building the Baseline Governance Profile first is a deliberate proof obligation — it
demonstrates the profile mechanism against a real framework before any industry-specific
profile depends on it.
