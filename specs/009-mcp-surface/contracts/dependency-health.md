# Contract: Dependency health and the two denials

**Feature**: `specs/009-mcp-surface`
**Status**: Planned
**Depends on**: ADR-0049 (Proposed — resolved by this feature); Principles II, III

## One owner of "healthy"

The health checker records reachability; everything else reads what it recorded (FR-006a).

Two components deciding what healthy means will drift, and a run resumed against a dependency
the other believes is down is precisely the failure suspension exists to prevent.

**Granularity is a named product**, as the tool registry names it. Per-workspace or
per-endpoint health is tempting and is a much larger claim on a customer's environment — it
would mean the checker enumerating their estate rather than asking whether a product answers.

**`UNKNOWN` is `UNHEALTHY`.** Guessing reachable is how a dead dependency gets called anyway.

**Persisted, not in memory.** A restart must not silently mean "everything is reachable
again"; a stale record reads as unknown rather than as either extreme.

**Recovery is hysteretic, failure is not.** One failure marks unhealthy; several consecutive
successes mark healthy. Marking unhealthy fast costs a suspension the sweeper resolves.
Marking healthy fast resumes every waiting run into a product that fails again, and each
cycle burns real budget against the run's maximum duration.

## The refusal is a hook, and placement is asserted

The gate runs **inside** the governed pipeline, beside governance, authority, and mirroring —
not as a pre-flight before it.

A check before the pipeline is a second refusal path, and a second refusal path is a second
authorization path wearing a practical-sounding name. It would also leave a run started
through some later transport ignoring a dependency the platform knows is down.

**The conformance row asserts placement, not just behaviour.** A pre-flight guard is
*obviously* cheaper — skip the pipeline for a call that will be refused anyway — and it works.
That is exactly why behaviour alone is not enough: the first person optimising a hot path
moves it, and nothing notices.

**No intent record is written** (FR-007). Attempting a call against a dead dependency writes
an intent that must later be resolved by re-observation — against the same dead dependency.
The bracket that makes interrupted steps resolvable becomes the thing that cannot be resolved.

## Two kinds of no

| Class | In the trail | Told to the model | Why |
| --- | --- | --- | --- |
| **Policy** | Yes | **No** | The governance boundary holding. An agent that treats it as an obstacle to route around inverts Principles II and III |
| **Availability** | Yes | **Yes** | Invites a legitimate alternative: write the Terraform, hand it back, say the workspace was unreachable |

This asymmetry is the subtlest thing in the feature. Getting it **backwards** — making scope
denials look adaptable — would actively train agents to look for another route, which is the
one behaviour the governance layer exists to prevent.

An operator must also be able to tell them apart: "not allowed" and "not reachable" send you
to different places, and a trail that blurs them wastes the investigation.
