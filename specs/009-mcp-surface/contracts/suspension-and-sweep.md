# Contract: Suspension and the sweeper

**Feature**: `specs/009-mcp-surface`
**Status**: Planned
**Depends on**: ADR-0049 (Proposed — resolved here); ADR-0026 (partially superseded); ADR-0048

## What replaces PARKED

`PARKED` meant "stopped for a human to resolve". ADR-0049 removes the category, so the state
goes rather than being renamed — the name would carry the human-in-the-loop connotation into
the state that most needs it gone.

| Was | Becomes | Resumable |
| --- | --- | --- |
| Grant expiry | `STOPPED`, reason recorded | No — an execution bound like any other |
| Unreachable dependency | `SUSPENDED`, naming the dependency | Yes — by the sweeper, never by a person |

**This changes a constitutionally-named gate row.** Quality Gates name *"grant-expiry
parking"*; it becomes grant-expiry **stop**. A constitution amendment with a Sync Impact
Report citing ADR-0049 ships in this feature. MINOR — a gate row is redefined, no principle
is — so no ADR-0016 quorum.

## A suspended run is a record, not a process

The container ends when its work ends, **including when that work ends in suspension**
(FR-011). It does not idle holding a slot while a dependency is down.

Resumption starts a **new allocation**, which is also what makes resume re-attest: a new
allocation has a new attested identity by construction (ADR-0048), so re-authentication falls
out of the lifecycle rather than being enforced by a rule someone could forget.

## The sweeper

Recovery is a platform-level event, so the response is platform-level: **one sweep resumes
every run waiting on that dependency**. No run polls, and no person is told to press anything.

It runs under the MCP service's own attested identity, and it never holds or forwards a run's
credentials — each resumed allocation manufactures its own. A sweeper carrying a credential
forward would reintroduce replay through the back door, after 005 spent a feature making it
structurally unavailable.

**Concurrency**: 005's single-writer fencing governs. Two sweeper instances resuming the same
run is the double-resume case that feature already closed — the resumed run supersedes, and
the loser's writes are rejected as a superseded holder's.

**Revocation wins.** A resumed run manufactures fresh authority and fails to obtain it if the
grant was revoked. Revocation is unilateral and immediate (Principle IV); the sweeper has no
path that could override it, because it never carries authority in the first place.

## Bounds

Suspension expires against the run's **existing** maximum duration (FR-013). Not a new
ceiling, no timeout that grants by default, no escalation that lowers a requirement.

A dependency down long enough to exhaust a run's whole budget indicates a failure well beyond
this platform's concern — the right outcome there is a stopped run and an alert, not a
platform that keeps trying.

## Nothing here notifies a human

The sweeper is the mechanism that makes humans *not* be in the loop (FR-014). Once it is
established what an agent and a person may reach, enforcement is continuous and automatic: the
harness denies what exceeds authority, records what happened, and alerts when something
warrants attention. **A human reads an alert and decides what to do next; they are never a
step a run is blocked on.**
