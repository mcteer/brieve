# ADR-0051: A turn is evidence; a thread is a view

- **Status**: Accepted (2026-07-29, decided by `specs/012-conversational-portal`)
- **Date**: 2026-07-29
- **Relates to**: [ADR-0034](0034-conversational-web-ui.md), [ADR-0035](0035-audit-as-a-governed-read-path.md), [ADR-0033](0033-four-transports-one-authorization-core.md), [ADR-0016](0016-control-groups-gate-authority-changes.md)
- **Requirements**: R4, R10, R13, R15

## Context

[ADR-0034](0034-conversational-web-ui.md) says threads are tenant-scoped run state,
persisted like any other run state and auditable by correlation ID. It does not say what
happens when a person wants a conversation gone, and that question turns out to decide the
whole design.

Two requirements pull against each other. A person may delete their conversation — an
ordinary expectation of any product with a message box, and one this platform has no
reason to refuse. And evidence may never be mutated or masked
([ADR-0035](0035-audit-as-a-governed-read-path.md)) — the property everything downstream
of the audit plane depends on.

If a thread *is* the record, those cannot both hold: deletion becomes a masking primitive,
handed to exactly the person with a motive to use it. If a thread is *not* the record, then
something else has to be, and it has to hold enough that deleting the thread loses nothing
an investigator needs.

There is a sharper version of the same question. A conversational surface accumulates
messages that start nothing — a person types, changes their mind, is refused, asks
something the platform will not do. Those are the messages an investigator most wants,
because they show intent that did not become action. They are also the ones a
thread-as-record design loses first.

## Decision

**Every accepted message is written to the audit trail before anything acts on it.**
`TURN_RECORDED` carries the message verbatim under the thread's correlation ID, and it is
written for all three accepted dispositions — dispatched, declined, and refused-on-scope.
A dispatched turn's event is that run's rationale: the only thing that answers *why did
this happen*.

**A thread is a readable view over those events, and is hard-deletable by its owner.**
Deleting it removes rows and masks nothing, because the trail holds what they held.
Deletion is itself an event (`THREAD_DELETED`), so the removal is in the chain rather than
merely permitted.

**Pre-acceptance refusals are recorded differently, and the difference is load-bearing.**
A message that exceeded the size bound or the rate window gets `TURN_REFUSED`, carrying the
message's *size* and never its content. Recording the content would make an append-only
store growable at whatever rate a caller can be refused — the bound protecting dispatch
would leave evidence unbounded. Recording nothing would make flooding invisible. The size
is what lets an investigator see the shape of an abuse attempt without the trail carrying
its payload.

**The ordering is the guarantee.** Evidence is written first, so the only surviving
inconsistency is an event with no row — which on a deleted thread is the point, and on a
live one is the crash window between two writes, where the trail's account wins. The
reverse, a row with no event, would let the view assert something the trail cannot support,
and is the one direction this design does not permit.

## Consequences

Both requirements hold at once, and neither is weakened to accommodate the other. A person
deletes a conversation and it is gone from their list; an investigator reconstructs the
whole exchange — including the messages that started nothing — from the trail alone.

Threads become droppable, like the run index before them: nothing durable depends on them,
so a schema change or a data loss in that table costs a reading, not a record.

### The cost, stated plainly

**A person's free text becomes permanent, append-only evidence.** There is no edit, no
redaction, and no expiry. If someone pastes a secret into a message box, that secret is in
the audit trail for as long as the trail is kept, and the only remedies are the ones that
apply to any leaked credential: rotate it.

The interface says so — the composer carries a notice that messages are recorded — which
makes it an informed cost rather than a hidden one. It does not make it a small one.

### The divergence from `redact_arguments`, owned rather than assumed

This platform already has a policy for free content entering the trail, and it is the
opposite of this one. `core/redaction.py` records tool arguments as **keys and content
hashes, never raw values**, on the reasoning that an argument may carry a secret and the
trail is not the place for it.

A turn's message is treated differently on purpose:

- **A message is the consent record; an argument merely parameterizes one.** "Why did this
  run happen" is answerable only from what the person actually said. A hash answers
  "something was said" and nothing else, which would make every dispatched run
  unexplainable and gut SC-004's reconstruction requirement.
- **The person authored it knowing it is recorded.** A tool argument is generated by an
  agent mid-run, often from data the person never saw; a message is typed by a human who
  is told, on the same screen, that it is kept.
- **The bound is small and the content is theirs.** 8 KiB, from one person, about their own
  work — not an arbitrary payload from an arbitrary source.

None of that makes the risk zero, and this record does not claim it does. **The residual
risk accepted is: a secret pasted into a portal message is permanent.** The mitigations are
the composer notice, the size bound, and `TURN_REFUSED` never carrying content — and the
security-maintainer sign-off on `specs/012-conversational-portal` is a sign-off on exactly
this acceptance, not on the feature in general.

If that trade should be revisited — a redaction pass over message payloads, a retention
window on `TURN_RECORDED`, a different bound — it should be revisited **by a superseding
record**, per Principle X, rather than by quietly changing what the event carries.

### What this does not decide

Retention of the audit trail itself, which is an operational policy this platform has not
yet written. Nothing here shortens or lengthens how long evidence is kept; it only decides
what enters it.
