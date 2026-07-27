# ADR-0049: Consent to start a run is consent to finish it; dependencies are monitored, not escalated

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

**An unresolvable step suspends the run; it does not wait on a person.** Re-observation
still governs, and a step whose outcome **cannot be determined** is still never guessed.
What changes is what happens next: the run records which dependency it could not reach and
suspends. It is resumed automatically when that dependency recovers.

**A run may wait on a machine condition; never on a human.** That distinction is the whole
of this decision. Waiting on something automatic clears itself; waiting on a person does
not. `PARKED` — "stopped for a human to resolve" — is removed. What replaces it is
suspension pending a *named dependency*, which something else is responsible for clearing.

**A suspended run is a record, not a running process.** The container ends when its work
ends — including when that work ends in suspension. It does not idle holding a slot while
a dependency is down. Resumption starts a **new allocation**, which is also what makes
resume re-attest: a new allocation has a new attested identity by construction
(ADR-0048), so the guarantee falls out of the lifecycle rather than being enforced.

**Suspension expires against the run's maximum duration** — the existing ceiling, not a new
one. A dependency down long enough to exhaust it indicates a failure well beyond this
platform's concern.

**Human authorization moves entirely to design time.** Registering an agent, changing its
privileges, and managing user and agent policy at the control-plane Vault remain
quorum-gated per ADR-0016. That is the loop humans are in, and it is the whole of it.

**Dependency availability is monitored, and known-unavailable dependencies are refused
upfront.** The harness monitors the reachability of the products agents operate. When one
is known down, tool calls against it are **denied before execution** rather than attempted
and observed to fail.

This is not an optimisation. Attempting a call against a dead dependency writes an intent
record that must later be resolved by re-observation — against the same dead dependency.
Refusing upfront means there is nothing to resolve. It also means one signal, raised once,
instead of every affected run independently rediscovering the same outage.

**An availability denial is a different kind of "no" from a policy denial, and they must
stay distinguishable.** A tool call refused for scope must NOT teach an agent to find
another route; that is the governance boundary holding. A call refused because a
dependency is down *invites* a legitimate alternative — writing the Terraform and handing
it back, rather than applying it. Only the availability class is model-visible as an
invitation to adapt. Blurring them would teach agents that denials are obstacles to route
around, which inverts Principles II and III.

**A sweeper resumes suspended runs when their dependency recovers.** Recovery is a
platform-level event, so the response is platform-level: one sweep resumes every run
waiting on that dependency. No run polls, and no person is told to press anything.

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

An earlier draft of this ADR described a cost that does not exist: that a run unable to
determine its own state loses work a human could have rescued by answering one question.
That framing survived because it *sounds* like a trade-off. It is not one — a person
asked whether a `terraform apply` succeeded has no way to answer except by reading the
same system the agent just failed to read. The rescue was imaginary, and writing it down
as a cost kept the human-in-the-loop premise alive in the reasoning after it had been
removed from the design.

The real answer is to keep trying until the platform knows. That is what suspension and
the sweeper are for.

**What this costs is machinery that does not exist yet, and it now has a likely home.**
The harness's MCP service — the persistent container that coding IDEs and other clients
talk to — is a **service** workload rather than a batch one: long-lived, with its own
workload identity, unlike the agent containers that end with their work. That makes it the
natural place for both the **dependency health checks** and the **sweeper**, since both
need to run continuously and neither belongs in a container that exists for one job.

**Checks run on the MCP service; health state is written to Postgres.** The denial itself
happens in the governed core, on the invoke path, inside an ephemeral agent container — so
it reads the state store rather than calling the MCP service.

That split is deliberate. Querying the MCP service on every tool call would put it in the
hot path of all agent work, and an availability check that fails when its own dependency is
unreachable is a poor shape for the component whose job is knowing what is unreachable.
Postgres already holds durable run state, is already reachable from every agent container
under the same credential path, and does not care whether the MCP service is up.

Until that machinery exists, the honest description is that this ADR is a decision rather
than a shipped capability, and a run that cannot observe has no automatic path back. That
gap belongs on the roadmap — not assumed closed by accepting this.

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

**A naming defect this surfaced.** `issue_grant` refuses a duration exceeding "the agent
definition's maximum run duration", but nothing resolves that from a definition — it is a
platform default of eight hours, taken as a parameter. Eight hours is the right value; the
message is wrong about where it comes from, and sends a reader looking for a definition
field that does not exist. Fix the language, not the number.

**Container lifetime is not run lifetime.** The eight hours bounds how long a run remains
*resumable*; it is not a reservation. An allocation exists to do work and ends when that
work ends — including when it ends in suspension. A five-minute job is a five-minute
container.

## Notes

The superseded rules were not careless. Requiring re-consent for lapsed authority is the
conservative reading of Principle IV, and parking rather than guessing is the conservative
reading of re-observation. Both were argued for, reviewed, and implemented on their merits.

What they missed is that "ask a human" is only conservative when a human is actually
available and actually informed. At the frequency an agent platform generates such
questions, it is neither — and a safety mechanism people learn to click through is worse
than one that never asks.

The sharper miss was one of layer. A run failing to reach a managed product is a *symptom*
of a condition the platform should already know: that product is down. Escalating it
per-run turns one outage into thousands of prompts, each describing the same fact and none
individually actionable. Monitor the dependency, refuse the calls, resume when it returns —
and tell someone once.
