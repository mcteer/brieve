# ADR-0049: Consent to start a run is consent to finish it

- **Status**: Proposed
- **Date**: 2026-07-26
- **Supersedes**: the re-consent and human-resolution rules of [ADR-0026](0026-delegation-grants-and-per-step-tokens.md) (the rest of that ADR stands)
- **Relates to**: [ADR-0016](0016-control-groups-gate-authority-changes.md), [ADR-0015](0015-control-plane-vault-as-trust-fabric.md), [ADR-0024](0024-durability-provider-seam.md)
- **Requirements**: R2, R3, R7

## Context

[ADR-0026](0026-delegation-grants-and-per-step-tokens.md) treats the delegation grant as
per-task human consent with a lifetime, and draws two consequences from it:

> If the grant has expired, the run **parks** for re-consent rather than resuming — an
> expired grant is a withdrawn permission, not an inconvenience.

and, as implemented in `specs/005-durable-execution`, a step whose outcome cannot be
determined by observation parks for a human to resolve.

Both put a person in the loop **during a run**. That reads as caution, and in a regulated
setting caution usually reads as correct — which is why it survived a specification, a
plan, two analyze passes, and an implementation without anyone flinching.

It is wrong for this platform, and the reason is not philosophical. An agent operating
infrastructure performs long, multi-step work; the whole point of durable execution is
that such work survives disruption. A run that stops mid-flight and waits for a human has
turned a durable execution engine into a ticketing queue. Multiply it by the number of
runs an estate produces and the human becomes the bottleneck the platform exists to
remove — while the *interruption* arrives at whatever hour the disruption happened, not
when anyone is available.

There is a second problem, quieter. A person asked to re-consent mid-run is being asked
about something they have no fresh context for: a task they authorized hours ago, paused
at a step they did not choose, described in terms of a checkpoint. That is not meaningful
consent. It is a dialog box, and people click through dialog boxes.

**Where a human genuinely belongs is earlier**: registering an agent, granting or changing
its privileges, and managing policy at the control-plane Vault. Those are deliberate,
low-frequency, and reviewable — and they are exactly [ADR-0016](0016-control-groups-gate-authority-changes.md)'s
subject.

## Decision

**Consent to start a run is consent to finish it.** Authorization is established before a
run begins — through the agent's registration, its ceiling, and the policy governing it —
and it holds for that run's duration. No run waits on a human.

Concretely, superseding ADR-0026:

**Grant expiry is a bound, not a withdrawal.** The delegation grant remains ceilinged by
the agent definition's maximum run duration, and a run reaching that ceiling **stops with
the reason recorded** — the same disposition as any other execution bound. It does not
park, and there is no re-consent. The two-level split ADR-0026 established survives
intact: short-lived per-step credentials manufactured under a longer-lived grant, with
resume re-authenticating rather than replaying.

**An unresolvable step stops the run; it does not wait.** Re-observation still governs: a
step observed to have taken effect is not repeated, one observed not to have is, and a
step whose outcome **cannot be determined** is still never guessed. What changes is what
happens next — the run stops, records what it knows, and a human investigates on their own
schedule. Nothing is pending on them.

**There is no waiting run state.** `PARKED` is removed. A run is active, completed,
stopped with a reason, or refused at start. Resuming after investigation is a *new run*,
which is also the honest description of what it is: fresh authorization, fresh context.

**Human authorization moves entirely to design time.** Registering an agent, changing its
privileges, and managing user and agent policy at the control-plane Vault remain
quorum-gated per ADR-0016. That is the loop humans are in, and it is the whole of it.

**After that, the control surface is audit and alerting — not intervention.** Once it is
established what an agent and a person may reach, enforcement is continuous and automatic:
the harness denies what exceeds authority, records what happened, and *alerts* when
something warrants attention. A human reads an alert and decides what to do next; they are
never a step a run is blocked on.

This is a real shift in where assurance comes from, and it should be said plainly rather
than implied. Under the superseded rules, some safety rested on a person being asked at the
right moment. It now rests on three things that do not depend on anyone being awake:
authority that cannot exceed its ceiling, enforcement that fails closed, and evidence
complete enough to reconstruct what happened. Alerting is how a human learns something
needs them; it is not how the system stays safe.

## Consequences

The platform gets simpler, which is the surprise. A waiting state is not just an enum
value — it implies a queue, a notification path, an owner, an escalation when nobody
answers, and a story for a run parked over a weekend. None of that has to exist now.

The cost is a real one and should not be glossed: **a run that cannot determine what it
did now stops rather than preserving the option to continue**. Work is lost that a human
could in principle have rescued by answering one question. That trade is accepted because
the alternative is worse in aggregate — a platform where any run might block on a person is
one whose throughput is bounded by human availability, and where the standing volume of
pending questions trains people to answer without reading.

It also puts real weight on alerting, which this platform does not yet have. A stopped run
that nobody is told about is a silent failure, and "audit and alerting" is currently half
a sentence and one implemented half. Until an alerting path exists, the honest description
is that stopped runs are *discoverable*, not *reported* — and that gap should be named on
the roadmap rather than assumed closed by this decision.

It also sharpens what evidence is for. A stopped run's audit trail is no longer a prompt
for someone to act on mid-flight; it is the record an investigator reads afterwards to
decide whether to start a new run. That is a weaker real-time signal and a better forensic
one, and it fits ADR-0018's grounded-reporting posture.

For ADR-0016 the change is a narrowing that makes it more coherent: Control Groups govern
*authority*, not *runs*. Their subject is who may widen a scope, restore revoked access, or
change claim-to-role mapping — deliberate acts a quorum can meaningfully review.

**In-flight cost.** `specs/005-durable-execution` shipped the superseded behaviour: FR-005,
FR-008, `RunState.PARKED`, `park_run`, and one of the seven durability conformance rows
(grant-expiry parking) implement re-consent and human resolution. Those need a change, and
the constitution's Quality Gates name that row explicitly, so it requires a constitution
amendment as well. Recorded here rather than discovered later.

## Notes

The superseded rules were not careless. Requiring re-consent for lapsed authority is the
conservative reading of Principle IV, and parking rather than guessing is the conservative
reading of re-observation. Both were argued for, reviewed, and implemented on their merits.

What they missed is that "ask a human" is only conservative when a human is actually
available and actually informed. At the frequency an agent platform generates such
questions, it is neither — and a safety mechanism people learn to click through is worse
than one that never asks.
