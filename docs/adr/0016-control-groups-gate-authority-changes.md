# ADR-0016: Control Groups gate what agents may become; hooks gate what agents do

- **Status**: Accepted
- **Date**: 2026-03-18
- **Relates to**: [ADR-0006](0006-in-process-fail-closed-enforcement.md), [ADR-0015](0015-control-plane-vault-as-trust-fabric.md), [ADR-0026](0026-delegation-grants-and-per-step-tokens.md), [ADR-0044](0044-authz-doctrine-and-credential-translation.md)
- **Requirements**: R2, R3

## Context

The hook pipeline ([ADR-0006](0006-in-process-fail-closed-enforcement.md)) governs
actions: every tool call is evaluated against the agent's authority at the moment it is
made. That is the right control for actions, and it is automated by necessity — an agent
that needed human approval for every tool call would deliver nothing.

But actions are not the only thing that matters. Raising an agent's ceiling, changing its
definition, writing directly to the trust fabric, or exercising break-glass access are
changes to *what the agent is permitted to become*. These are rare, high-consequence, and
frequently the first step in an attack: an attacker who can quietly raise a ceiling does
not need to defeat the hook pipeline at all, because every subsequent action will be
legitimately within scope.

Applying the same control to both is wrong in both directions. Requiring human approval
for routine actions destroys the product's value; automating authority changes destroys
its security claim.

There is also a specific asymmetry that matters during an incident. Requiring quorum to
*revoke* authority would mean an active compromise stays live while approvers are found —
a control that fails in the worst possible direction under exactly the conditions it
exists for.

## Decision

**Two different controls for two different kinds of change.**

> **Hooks gate what agents do. Control Groups gate what agents may become.**

**Authority changes are quorum-gated** through the trust fabric's multi-party approval
mechanism: ceiling changes, definition changes, manual writes to the control plane,
break-glass access, and reactivation of a suspended agent all require multiple approvers
before taking effect.

**Instance operations are automated within approved definitions.** Scaling, restarting,
scheduling, and registering instances of an already-approved definition proceed without
human involvement — the approval already happened, at the definition.

**Revocation is unilateral and immediate.** Any authorized individual can revoke, alone,
instantly. Only *restoration* requires quorum. The control is deliberately asymmetric:
easy to make safe, hard to make permissive.

## Consequences

The dangerous operations require collusion rather than a single compromised credential,
and the routine ones stay frictionless. That combination is what makes the platform both
safe and usable — either control applied universally would fail.

The asymmetry on revocation matters most in the moment nobody is prepared for. During a
suspected compromise, containment is one person's decision and takes effect immediately;
the deliberation happens on the way back, which is the correct ordering.

Placing the quorum requirement at the *definition* rather than the *instance* is what
makes automation safe at runtime: the reviewed artifact is the definition, so instances
of it need no further approval, and the audit question "what was this agent permitted to
do" has a single reviewed answer.

The costs are organizational rather than technical. Quorum requires that enough approvers
exist and are reachable, which is a real operational commitment — and an under-staffed
approver pool turns into either a bottleneck or a rubber stamp, both of which defeat the
control. Break-glass procedures need to be designed, rehearsed, and audited, because a
quorum control with an untested emergency path fails when it is needed.

There is also an adoption cost: organizations must decide who holds approval authority
before they can operate the platform, which surfaces governance questions earlier than
they might prefer. That is the correct time to surface them.
