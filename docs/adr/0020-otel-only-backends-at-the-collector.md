# ADR-0020: OTel-only in core; observability backends attach at the collector

- **Status**: Accepted
- **Date**: 2026-04-15
- **Relates to**: [ADR-0009](0009-adlc-stages-and-observability-planes.md), [ADR-0018](0018-grounded-reporting.md), [ADR-0021](0021-connectivity-tiers.md), [ADR-0035](0035-audit-as-a-governed-read-path.md)
- **Requirements**: R4, R10

## Context

Observability platforms want to be integrated deeply: install the SDK, and get
richer data than a generic pipeline provides. For most software that trade is fine.

Here it is not. Three problems compound.

**Credentials in the wrong place.** A vendor SDK in the agent runtime means the runtime
holds credentials for an external service. In a platform whose central claim is that the
runtime holds no standing credentials to anything, that is a contradiction sitting in the
hot path.

**Capture policy enforced too late.** Prompts and completions may contain data that must
not leave the boundary. If each SDK decides what it sends, redaction is enforced in as
many places as there are SDKs, and a misconfigured one exfiltrates before anything can
stop it.

**Vendor selection in core.** Naming a vendor in core code makes swapping one a code
change, which regulated adopters with incumbent stacks will simply refuse.

There is a fourth consideration specific to the audit plane. Traces and metrics are
operational telemetry and can reasonably leave the boundary; **audit is evidence**, and
evidence that egresses by default is a compliance problem in several of the target
verticals regardless of the destination's quality.

## Decision

**The core emits standard OpenTelemetry only. No vendor observability SDKs in core.**

**Backends attach at the collector.** Whatever an organization runs — a default backend
where they have no incumbent, or their existing stack — is configured at the collector,
outside the agent runtime. Consequences: pods never hold observability credentials, and
**capture policy is enforced once, before any egress**.

**The audit plane never egresses by default**, and hosted services are off by default in
regulated profiles. Export to a SIEM is an explicit, configured act.

**A default is not a dependency.** A default backend exists so that a fresh install is
useful immediately, but the flywheel, fidelity checks, and attestation all function with
zero external backends. Evaluation follows the same pattern: a code-first default behind
a thin provider interface, not a vendor commitment.

Framework-native tracing feeds this pipeline through the adapters and inherits its
capture policy; it never ships independently.

## Consequences

Swapping observability backends is collector configuration, not a code change — which is
what makes the platform adoptable by organizations with an incumbent stack, and what
keeps the Federated profile honest.

Enforcing capture policy at a single point before egress is a far stronger property than
enforcing it in every SDK. It is also auditable: there is one place to inspect and one
configuration to review.

Keeping audit inside the boundary by default means the compliance-sensitive plane behaves
conservatively unless someone deliberately decides otherwise, which is the correct default
direction for evidence.

The costs are ordinary. Standard OTel gives less vendor-specific richness than a native
SDK would, and some backend features are unavailable or degraded through a generic
pipeline. The collector becomes an operational component that must be configured
correctly — a misconfigured collector is a silent observability outage, which is
survivable but unpleasant.

There is also a discipline cost that recurs: every future integration request will arrive
as "just add this SDK," and the answer is always the collector.
