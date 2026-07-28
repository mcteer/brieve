# Contract: the run index

**Feature**: `specs/011-api-operations`
**Status**: Planned

## What it is

An insert-only table answering "what has this person started" — the question no durable
store could answer, because `checkpoints` was built for resume and resume never needed a
subject. Written by `dispatch()` from arguments it already receives; read by list, result,
and stop.

## What it is not, stated because each has a failure mode

**Not run state.** State lives on the checkpoint, which stays authoritative. The index
row is written once and never updated; a listing joins state in at read time. An index
that carried state would be the second writer the checkpoint's row lock exists to prevent.

**Not read by resume.** Resume has the checkpoint and needs nothing else. The moment
resume reads the index, the index stops being droppable — and droppable is a property
worth keeping for a table whose only job is enumeration.

**Not backfilled.** It starts empty and lists runs dispatched after this feature. A
backfill from audit would launder the forensic path through a migration script — the exact
dependency US3 exists to remove, one step removed. The empty first page is correct, and
this line exists so nobody "fixes" it.

**Not the sweeper's index.** `suspended_runs` (009) is "find runs awaiting a product";
this is "find runs by starter". Two indexes over one run population is a recorded
coherence question (research, remaining unknowns) — deliberately unresolved until
something forces it, and the package docstring carries it.

## The divergence row

The index and the audit trail are two accounts of what ran, written at the same moment by
the same dispatch. The conformance contract carries a row asserting a dispatched run
appears in **both** — because two accounts that can disagree quietly is how an
investigator ends up trusting the wrong one. The row exists so divergence is loud.

## Who writes, who reads

| Path | Access |
| --- | --- |
| `dispatch()` | INSERT, in the same motion as the dispatch |
| List / result / stop operations | SELECT, always tenant-filtered first |
| Resume, sweeper, evidence role | **Nothing.** The evidence role gets the same REVOKE treatment `dependency_health` got — operational state in the same database is not evidence |
