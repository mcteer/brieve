# ADR-0026: Long-running execution — delegation grants, per-step tokens, resume as re-observation

- **Status**: Accepted; partially superseded by [ADR-0049](0049-consent-to-start-is-consent-to-finish.md) (2026-07-28)
- **Date**: 2026-05-13
- **Relates to**: [ADR-0016](0016-control-groups-gate-authority-changes.md), [ADR-0018](0018-grounded-reporting.md), [ADR-0024](0024-durability-provider-seam.md)
- **Requirements**: R2, R3

## Context

A task that runs for hours collides with a security model built on short-lived credentials.
Tokens that expire in minutes are correct — they bound the damage of a leak — but a run
that outlives its token has to do *something* when it resumes.

The tempting answers are all wrong. Storing a long-lived credential in the checkpoint gives
an attacker who reads checkpoint storage exactly what they need. Replaying the original
token after resumption defeats expiry entirely. Extending token lifetime to cover the
longest plausible run inverts the security model to accommodate the slowest case.

Resumption has a second hazard independent of credentials. A run interrupted mid-step does
not know whether the step completed — the infrastructure change may have applied, the pull
request may have opened, the secret may have been written. Replaying it risks a duplicate
side effect; skipping it risks an incomplete run. Neither is acceptable when the side
effects are infrastructure changes.

And a partitioned node may believe it is still the owner of a run that has already resumed
elsewhere, producing two writers for one task.

## Decision

**Two-level authority.** The user's **delegation grant** — their consent to the task,
ceilinged by the definition's maximum duration — is the durable object. **Per-step tokens
are manufactured under it as needed** and expire normally.

> **Checkpoints hold state, never credentials.**

**Resume re-authenticates.** After disruption, the workload re-attests, re-binds to the
run, and re-exchanges under the surviving grant. If the grant has expired, the run
**parks** for re-consent rather than resuming — an expired grant is a withdrawn permission,
not an inconvenience.

**Resume is re-observation, never re-execution.** On resumption the platform re-reads the
state of external systems to determine what actually happened, reusing the same receipts
grounded reporting depends on ([ADR-0018](0018-grounded-reporting.md)). Non-idempotent
tools are bracketed by intent and result records, so an interrupted call can be resolved
by observation rather than by guessing.

**A single-writer lease with fencing** ensures a resumed run invalidates any zombie: the
partitioned instance's writes are rejected, not merely raced.

Execution is **bounded**: maximum duration, loop limits, and a stuck-wait watchdog, so a
run cannot consume authority indefinitely.

## Consequences

Multi-hour runs survive disruption without weakening the credential model — which is the
combination that makes long-running agentic infrastructure work possible at all in a
regulated setting. The grant is the human-meaningful unit ("I consented to this task"),
and it is separable from the technically-meaningful unit (a token valid for minutes).

Parking on grant expiry rather than resuming is the behavior that will surprise operators
most, and it is deliberate. A run that resumes days later under a consent the user has
forgotten giving is not a feature.

> **Superseded by [ADR-0049](0049-consent-to-start-is-consent-to-finish.md).** A run
> reaching its ceiling now **stops with the reason recorded**; there is no re-consent, and
> `PARKED` no longer exists. The paragraph above is kept rather than rewritten because
> Principle X requires supersession be recorded, not edited in place — and because the
> reasoning it contains is the reasoning ADR-0049 had to answer. Editing it away would
> leave that ADR arguing against nothing.

Re-observation is what makes resumption safe with irreversible side effects, and it is
also the expensive part: every resumption pays the cost of re-reading external state, and
every tool must expose enough for that reading to be conclusive.

The costs concentrate in implementation difficulty. Intent-and-result bracketing has to be
threaded through every non-idempotent tool, and getting it wrong produces exactly the
duplicate side effects it exists to prevent. Fencing must be correct under partition,
which is the hardest thing here to test and the reason the conformance suite includes
partition-plus-double-resume as a mandatory scenario.

None of these properties are optional for a durability provider: they are defined above
the interface ([ADR-0024](0024-durability-provider-seam.md)) and asserted identically
against every implementation.

## Superseded parts

[ADR-0049](0049-consent-to-start-is-consent-to-finish.md) supersedes exactly two rules from
this ADR, and **nothing else here is affected**:

1. **Grant expiry parks for re-consent.** Now: the run stops, reason recorded.
2. **A step whose outcome cannot be determined parks for a human to resolve.** Now: the run
   suspends naming the dependency it could not reach, and a sweeper resumes it on recovery.

**What stands, and it is most of this ADR:** the two-level split of a longer-lived
delegation grant and short-lived per-step credentials; resume as re-observation rather than
replay; intent-and-result bracketing; single-writer fencing. ADR-0049 changes what happens
when a run *cannot proceed* — not how authority is structured or how resumption is made
safe.

The distinction matters because "superseded" read loosely would suggest the credential
model was revisited. It was not. ADR-0049 removes the human from the loop; it leaves the
mechanism that makes removing them safe entirely intact.
