# ADR-0021: Connectivity tiers are a third deployment axis

- **Status**: Accepted
- **Date**: 2026-04-22
- **Relates to**: [ADR-0007](0007-lean-and-federated-profiles.md), [ADR-0020](0020-otel-only-backends-at-the-collector.md), [ADR-0022](0022-qualified-model-matrix.md), [ADR-0030](0030-pinned-versus-consulted-artifacts.md)

## Context

The platform already varies along two axes: deployment profile (Lean or Federated) and
vertical (a policy and content profile). Network connectivity is a third, and it is
independent of both — a Lean deployment in a public-sector estate may have no egress at
all, while a Federated one in the same industry may be fully connected.

Connectivity is not a minor configuration difference. It determines whether the platform
can reach frontier model APIs, whether reference guidance can be fetched live, whether
hosted observability is possible, and whether artifacts can be pulled from upstream
registries. Several of those are load-bearing for features designed on the assumption
that the network is there.

The failure mode to avoid is a platform that technically installs in a restricted
environment but degrades in undocumented ways — where the honest answer to "does the
guidance layer work air-gapped" is "sort of," discovered after deployment.

## Decision

**Three connectivity tiers, orthogonal to profile and vertical:**

- **Connected** — the default; egress permitted.
- **Restricted** — proxy-only, allowlisted egress.
- **Air-gapped** — no egress.

Each tier has **defined substitutions rather than degradations**. Air-gapped estates
substitute a self-hosted product deployment for the hosted one, on-premises inference
behind the model gateway for frontier APIs, the self-hosted telemetry and code-first
evaluation floor for hosted services, and mirrored signed artifacts for live upstreams.
Reference guidance moves from live retrieval to date-stamped snapshots
([ADR-0030](0030-pinned-versus-consulted-artifacts.md)).

**Each release ships as a signed, SBOM'd bundle** — images, charts and modules, pinned
skills, policies, guidance snapshots with their pre-computed indices, enablement material,
evaluation suites, and where applicable the model — verified by signature and imported
through the organization's own transfer process. Preflight checks operate fully offline.
Air-gapped estates ride the long-term-support channel by default.

**Per-model evaluation qualification is mandatory**, not advisory: no air-gapped claim
ships without a passing evaluation matrix on the model that estate will actually run
([ADR-0022](0022-qualified-model-matrix.md)). Inside the boundary, the developer surface
is the harness's own tool server plus the CLI.

## Consequences

Restricted and air-gapped estates get a supported configuration with stated substitutions
rather than a degraded connected one, and the differences are documented before deployment
rather than discovered after. For public-sector and defense-adjacent adopters this is
frequently the difference between adoptable and not.

The mandatory evaluation requirement prevents the most likely quiet failure: assuming that
a pack qualified against a frontier model behaves equivalently on a smaller self-hosted
one. It usually does not, and the eval matrix is what turns that from a surprise into a
release gate.

The costs are substantial. Every feature must be designed with an air-gapped answer, which
constrains design choices that would otherwise be free — and features whose answer is
"unavailable offline" must say so explicitly. The signed bundle is real release machinery
with its own build, signing, and verification path, and it must stay in step with every
release.

Testing multiplies: the connected path and the offline path are different code paths, and
only exercising the former means the latter breaks silently between releases. Offline
preflight in particular has to be maintained as a first-class capability, because it is
the only self-check an air-gapped operator has.
