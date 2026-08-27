# Phase 0 Research: A finished authoring run leaves no proposal behind

**Feature**: 052 | **Date**: 2026-08-27 | **Spec**: [spec.md](spec.md)

Every Technical Context unknown is resolved here. Two findings (R6, R7) were not anticipated
by the spec: one removes a requirement's subject, and one adds work the spec did not scope.

---

## R1 — The trigger point already exists, and it is already in the right place

**Decision**: the payload scrub goes at
[entrypoint.py:1500](../../src/surfaces/dispatch/entrypoint.py#L1500), beside the intents
scrub — but **gated to the proposer branch only**, which the intents scrub is not.

**Rationale**: the call site reads:

```python
if authoring_role(...) == PROPOSER:
    published = _publish_the_proposal(run, checkpoint=checkpoint, registry=registry)
    ...   # "_publish_the_proposal already wrote the terminal payload (PR URL, or a phase failure)"
else:
    checkpoint_run(run, payload=dict(checkpoint.payload))

if authoring_role(...) is not None:      # <-- BOTH branches reach this
    scrubbed = scrub_authoring_requests(durability, run_id=blob_id)
```

FR-010's trigger is therefore already implemented for intents, and the terminal payload has
already been written by the time control reaches that line. The payload scrub rewrites what
`_publish_the_proposal` just wrote.

**The gating differs, and this is the load-bearing part.** `authoring_role(...) is not None`
is true in the **analyzer** task as well. That is safe for intents — the SQL clears closed
brackets only — and would be a defect for the payload: the analyzer's checkpoint *is* the
handoff the proposer will read, and scrubbing it there would make every publish resume with
nothing to publish. That is precisely US3's failure, reachable by copying the existing gate one
line down.

**Alternatives rejected**: a new terminal-state hook (the site already exists, and a second
place a run can be declared finished is the fragmentation Principle VII names); scrubbing
inside `_publish_the_proposal` (it has already returned by the time the payload is final, and
putting retention inside publishing couples two decisions that should move independently).

---

## R2 — The manifest FR-009 wants is already in the payload

**Decision**: preserve `files[].path` and the existing `provenance` list. Add nothing.

**Rationale**: `proposal_payload`
([authoring.py:162-182](../../src/surfaces/dispatch/authoring.py#L162-L182)) already writes a
`provenance` list, and a real run's looks like this:

```
'Run: `propose-1df2fcf1bfa9663b`',
'Analysed at commit `8e97b19acc596a4a6ced42af3a91449b15180e86`',
'Consulted 1 subject path(s): `README.md`',
'`src/config/vaultConfig.js` — `59eab8f7cb9bac1fe05b328bd6c7985f9755a399b2fe5ba7225292e1d7d56f12`',
'`src/integrations/vault/vaultClient.js` — `0f3aef65222672363f83f0c39ec9347d7e170dd045d149a2ec8ffd91abd2e2a5`',
```

Path and content digest, per file, already recorded. So FR-009 is a **preservation**
requirement rather than an addition: the scrub must not remove `provenance`, and a reviewer can
already prove a merged pull request is byte-identical to what the run proposed.

This is why the spec's third clarification was cheap to answer the way it was. The
alternative — "paths only, no digests" — would have meant *deleting* a field that already
exists, which is a stranger act than keeping it.

---

## R3 — The code already claims this feature works

**Finding, not a decision.** `proposal_payload`'s own docstring says:

> Files carry their bodies: the publishing task cannot recompute them, having no subject. That
> is a deliberate widening of what a checkpoint holds, bounded by the same rule the trail
> keeps — this is the control plane, not the append-only store, **and the run's terminal scrub
> (FR-033) removes it.**

The last clause is false today. The widening was taken deliberately and bounded by a scrub
that was never extended to the thing being widened.

Recorded because it is the same shape 051 removed from the Terraform phase cards — a comment
asserting a guarantee nothing performs — and because the docstring is the natural place to
notice this and nobody did. The implementation must make the sentence true rather than delete
it.

---

## R4 — No new provider method

**Decision**: a pure function in `core/authoring/retention.py` produces the scrubbed payload;
the entrypoint saves it through the existing `DurabilityProvider.save`.

**Rationale**: `save` upserts by `blob_id`
([postgres.py:118-130](../../src/core/durability/postgres.py#L118-L130) —
`ON CONFLICT (blob_id) DO UPDATE SET payload = EXCLUDED.payload`), so rewriting a checkpoint is
an operation the seam already provides and every run already exercises.

The intents scrub needed `scrub_closed_arguments` on the provider because it is a bulk `UPDATE`
across rows selected by a join — genuinely SQL work. This is one blob the caller already holds.
Adding a second provider method would widen a sealed-core seam (ADR-0024, Principle V) to do
something the seam already does.

**The split matters**: *what counts as content* is authoring knowledge and lives beside
`CONTENT_BEARING_TOOLS`; *how a payload is stored* is the provider's. Putting field selection
in SQL would put authoring knowledge in the durability provider, which is the layering error
`AGENTS.md` names.

**Consequence for testing**: 041's Postgres leg exists because in-memory clears a field for
free and would pass whether or not the SQL was written. That argument does not transfer — there
is no new SQL — so the equivalent row here asserts the **round trip**: save a scrubbed payload,
read it back from the real store, and confirm the bodies are gone from the stored JSON rather
than only from the object.

---

## R5 — What "terminal" means, precisely

**Decision**: the scrub fires after `_publish_the_proposal` returns 0, in the proposer task.

**Rationale**: `_publish_the_proposal` writes the terminal payload itself — the comment at the
call site says so, and explains that re-saving `checkpoint.payload` afterwards once restored
the analyzer snapshot and wiped `pr_url`. So the ordering is: publish → terminal payload
written → scrub rewrites it.

A scrub placed before publish would clear what publish is about to read. A scrub that
re-derived the payload from `checkpoint.payload` would resurrect the analyzer snapshot, which
is a defect this file already records somebody hitting.

**The spec's assumption is confirmed**: terminal state is reached only after publish. It is
recorded as an assumption rather than a fact of nature because the ordering is a property of
this code, not of the concept.

---

## R6 — FR-007's case may have no subject

**Finding.** The spec requires a run refused at Judge to be scrubbed on the same terms as one
that published. Measured against the store, a Judge-refused run **never composes a proposal**:
control returns before Propose, so `authoring_proposal` is never written.

The one refused run in the store (`propose-0db98c51d549e674`, Judge failed) carries progress, a
reason, and the task message — no file bodies, no proposal.

**Consequence**: FR-007 is satisfied vacuously, and a row asserting it would pass without
exercising anything — the passing stub ADR-0047 forbids. The row must instead assert the
*reason* it is vacuous: that a refused run's payload contains no authored content in the first
place. That is a real property and it can fail; "the scrub cleared a refused run's proposal" is
not, because there is none to clear.

**This is worth a spec sentence** and is carried to analyze rather than fixed silently.

---

## R7 — Six existing checkpoints hold customer content, and the spec does not say what to do

**Finding, and it adds scope.** Measured against the live store:

| Checkpoints | Holding a proposal | State |
| --- | --- | --- |
| 235 | **6** | `completed`, all of them |

Roughly 81 KB of authored file bodies across six runs, every one already terminal.

Two things follow.

**The never-terminal gap FR-011 records has zero instances today.** Every proposal-bearing
checkpoint reached terminal state, so the case FR-011 leaves open is real but currently empty.
That correctly sizes the follow-up: worth doing, not urgent.

**But the six existing rows are not covered by a forward-only scrub**, and SC-001 says *no*
completed authoring run leaves a body — 100%. The conformance row from #219 sweeps the whole
table, not runs created after the change. So either these six are cleared or the row stays red
and the feature has not closed the issue it was written for.

**Decision**: this feature clears them, as a one-time backfill applying the same function to
existing terminal checkpoints. Rationale: it is the same operation on the same shape of data;
leaving known customer content in the store while shipping a feature to prevent more of it
would be a strange place to draw a line; and the acceptance signal is a sweep of the live
store, which cannot distinguish "prevented" from "already there".

**Alternatives rejected**: scoping the row to new runs (it would stop being the signal #219
raised, and would need a cutoff nobody can verify later); manual operator cleanup (unrepeatable,
and the next deployment with history has the same problem); leaving them (SC-001 says 100%).

**Carried to analyze**: the spec has no requirement for this. It needs one.

---

## R8 — Nothing downstream reads the proposal after publish

**Decision**: no consumer migration is needed.

**Rationale**: `PROPOSAL_PAYLOAD_KEY` has exactly two readers —
`proposal_from_payload` (the proposer, before publishing) and the entrypoint that writes it.
No portal template, no report compiler, and no API operation reads it. So clearing the bodies
after publish breaks no existing path.

`proposal_from_payload` reads `body` from each file and would raise on a scrubbed payload. That
is correct and should stay: it is only called before publishing, and a scrubbed payload
reaching it means the ordering broke. A row asserts that reading a scrubbed payload fails
loudly rather than reconstructing an empty proposal.

---

## Resolved unknowns

| Unknown | Resolved by |
| --- | --- |
| Where the scrub fires | R1 — beside the intents scrub, proposer branch only |
| Whether the analyzer must be excluded | R1 — yes, and copying the existing gate is the trap |
| What the surviving manifest is | R2 — `files[].path` plus the existing `provenance` |
| Whether a provider method is needed | R4 — no; `save` already upserts by `blob_id` |
| What the Postgres row asserts without new SQL | R4 — the stored-JSON round trip |
| Ordering against publish | R5 — after `_publish_the_proposal` returns 0 |
| Whether the refusal path has a subject | R6 — no; the row must assert why |
| Existing rows | R7 — six, all terminal; backfilled by this feature |
| Downstream consumers | R8 — none |
