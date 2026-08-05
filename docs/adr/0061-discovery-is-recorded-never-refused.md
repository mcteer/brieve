# ADR-0061: A search for a tool is recorded, and can never be refused

- **Status**: Accepted
- **Date**: 2026-08-05
- **Amends**: the "no audit change" clause of [ADR-0040](0040-deferred-tool-disclosure.md)
- **Relates to**: [ADR-0006](0006-in-process-fail-closed-enforcement.md), [ADR-0009](0009-adlc-stages-and-observability-planes.md), [ADR-0041](0041-code-mode-requires-hook-parity.md), [ADR-0047](0047-conformance-gate-rows-attach-as-features-land.md)
- **Requirements**: R4, R10, R13

## Context

[ADR-0040](0040-deferred-tool-disclosure.md) made deferred disclosure the default posture
and was careful to bound what it changed. Its Decision says so in one sentence: **"No
registry, hook, or audit change. Every tool remains registered, every call passes the full
pipeline, every decision is audited. What changes is when the schema enters context."**
That sentence is what makes deferral a pure optimization, and it was correct about the
thing it was guarding — deferral must not become a second authority path.

Building it (036) surfaced a question that record did not face, because in 2026-07 the
mechanism was a plan rather than an implementation. Under deferral a model does something
it has never done before: it **searches**. It emits a query for a capability it has not
been shown, and the platform answers with a set of tool names — sometimes the empty set.

That act is invisible everywhere. The tool call that may follow is recorded exactly as it
always was; the search that preceded it is recorded nowhere. So the trail can show that an
agent called `delete_bucket` and cannot show that it spent four searches looking for a way
to delete something before finding it — or, more sharply, that it searched repeatedly for a
capability it was never granted and never found. **An empty search matches nothing, changes
nothing, and is the single most interesting thing a model can do under deferral**, because
it is intent without action.

The tension is that recording it contradicts ADR-0040's own words. Two wrong ways out were
available: ship the recording and leave the ADR saying the opposite, or drop the recording
to keep a sentence true. The first is the defect
[ADR-0060](0060-three-transports-the-cli-is-withdrawn.md) closed one level up a day earlier
— a governing document asserting a shape the platform does not have. The second discards
evidence to protect prose.

## Decision

**A search is recorded as an observation. Nothing may refuse it.**

Two halves, and both are load-bearing.

**Recorded.** Every search writes a `DISCOVERY_OBSERVED` entry carrying the queries, the
tool names matched, and how many deferred tools remain undisclosed. Names only — never the
schemas the search disclosed, which go to the model and not to the trail. An empty match is
written like any other, because the search that found nothing is the one worth reading.

**Never refused.** Discovery is not a decision point. It has no allow/deny, no reason code,
and no path by which policy can decline it. A search does not consume authority, does not
narrow scope, and does not alter what the run may do. Structurally this means a search never
reaches the governed tool entry at all: the search layer sits outside the terminal
governance wrapper and answers its own meta-tool without delegating inward. The exemption is
**positional, never a match on the tool's name** — a name-based exemption is a bypass anyone
can create by registering a tool called `search_tools`.

**The audit record is distinct from any tool-call record**, so no reader can mistake *"the
model looked for a way to delete a bucket"* for *"the model attempted to delete a bucket"*.
One is intent; the other is an act; a flag on a shared event type would have blurred them.

**This amends ADR-0040's "no audit change" clause and nothing else.** Deferral still makes
no registry change and no hook change; every tool remains registered; every *call* still
passes the full pipeline and is audited exactly as before. What is now also true is that the
*search* leaves a trace. ADR-0040's Decision section is not edited — records are append-only
— and its status line points here.

## Consequences

The trail gains a class of evidence the platform could not previously produce: what an agent
went looking for, including what it never found. Under eager disclosure this signal did not
exist to lose, because a model that can see everything never searches. Deferral creates the
signal and this record keeps it.

**Disclosure stays outside the authority path, which is the property worth protecting.** The
reason ADR-0040 could call deferral a pure optimization is that it changes what a model
*knows about* and never what it may *do*. Making a search refusable would have ended that: a
policy that can decline a search is a policy deciding what a model may know, which is a
second authority surface with different inputs and different failure modes from the one that
decides what it may do. The recording is free of this; a decision would not have been.

**It costs a small, permanent volume of records.** A run under deferral writes entries no
eager run does. They are names and counts rather than payloads, and the trail is
append-only, so the cost is real and bounded. Worth naming rather than discovering.

**Half a signal.** A search that matched nothing tells you the model wanted something it
could not find; it does not tell you the model would have used it. Nothing here should be
read as an intent-detection mechanism — it is a record of a question, and a question is not
a plan. Overreading it would be the confabulation this platform legislates against
elsewhere.

**Obligation discharged in the same change.** The `DISCOVERY_OBSERVED` member is a
sealed-core addition under Principle V and carries the approved spec and security-maintainer
review that principle demands, alongside `PROGRAM_SUBMITTED` (ADR-0041, same feature).

## Notes

Propagated with this record: `src/core/audit/schema.py` (the member and its argument),
`docs/adr/0040-deferred-tool-disclosure.md` (status line only — the Decision section is
untouched), `docs/adr/README.md`, and 036's conformance contract, where D5 asserts the
recording and D6 asserts that the exemption is positional rather than a name match.

The shape of this amendment — a new record pointing at an old one whose Decision stays
intact — is [ADR-0060](0060-three-transports-the-cli-is-withdrawn.md)'s mechanism, used
here for the second time. It is worth keeping: the alternative that keeps suggesting itself,
editing the original to match current behaviour, destroys the record of what was believed
when the decision was made.
