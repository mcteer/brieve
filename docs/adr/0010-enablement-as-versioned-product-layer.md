# ADR-0010: Enablement is a versioned product layer, not documentation

- **Status**: Accepted
- **Date**: 2026-02-26
- **Relates to**: [ADR-0009](0009-adlc-stages-and-observability-planes.md), [ADR-0013](0013-adopt-agent-security-framework-taxonomy.md), [ADR-0027](0027-tiered-capabilities.md)
- **Requirements**: R14

## Context

The platform's premise is that expert operational judgment can be captured once and made
available to everyone. That premise cuts both ways: the same is true of the judgment
required to *operate the platform itself*. An organization that installs it and receives
no transfer of ownership ends up dependent on whoever installed it — which is exactly the
bottleneck the product exists to remove, relocated one level up.

The conventional answer is documentation, and the conventional outcome is that
documentation drifts from the software, has no owner, and describes a version nobody is
running. There is no gate that catches stale enablement material, because documentation
is not part of any release.

There is a related failure specific to this kind of platform. The lifecycle
([ADR-0009](0009-adlc-stages-and-observability-planes.md)) assigns work to roles —
someone owns policy, someone owns packs, someone approves authority changes. If those
roles are never named or handed over, they default to the implementer, and the
organization never actually takes possession of its own governance.

## Decision

**Enablement is a versioned layer of the product**, released and compatible-tracked like
any other component — not a documentation set maintained beside it.

It carries **named ownership roles** rather than generic audiences: the platform
engineer who owns the enclave, the policy owner, the pack author, the approver on
authority changes. Each role has a defined scope and a defined transfer point.

Progress is measured by **objective graduation** — demonstrated capability against
defined criteria — rather than by attendance or completion. An organization has taken
ownership of a stage when it can perform that stage unaided, and that is testable.

The path is a maturity ladder: **Operate → Extend → Govern → Optimize.** Operate the
governed golden paths; extend them with your own packs, hooks, and policy; govern the
platform's authority decisions yourself; then optimize using your own production
telemetry.

## Consequences

Enablement material versions with the software, which means it can be gated: an
enablement layer that no longer matches the release is a release blocker rather than a
quiet inaccuracy. It also gets an owner, because a released component must have one.

Naming roles makes the handover concrete and its absence visible. "Who is the policy
owner" has an answer or it does not, and if it does not, the organization has not
completed that rung — which is useful information early rather than discovered during an
audit.

The ladder gives adopters a defensible sequence. Attempting to govern authority changes
before operating the golden paths reliably is a common and expensive mistake; the ladder
makes the ordering explicit.

The cost is real production work. Enablement content must be authored, kept current
against every release, and tested — which competes for the same effort as features.
Objective graduation is also harder to build than a course: it requires defining what
demonstrated competence looks like for each role and providing a way to demonstrate it.

The tiered capability model ([ADR-0027](0027-tiered-capabilities.md)) is the mechanism
that makes the ladder operational rather than aspirational — competency tiers in the
product line up with rungs on the ladder, so progression is enforced by what a definition
is permitted to pin, not only by training.
