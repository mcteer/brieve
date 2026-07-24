# ADR-NNNN: Short noun phrase describing the decision

- **Status**: Proposed | Accepted | Superseded by [ADR-NNNN](NNNN-slug.md)
- **Date**: YYYY-MM-DD
- **Supersedes**: ADR-NNNN (omit if none)
- **Relates to**: ADR-NNNN, ADR-NNNN (omit if none)
- **Requirements**: R# (omit if none)

## Context

The forces that made this a decision rather than an obvious call: constraints,
conflicting goals, what the alternatives were, and what was true at the time. Write for
someone joining in two years who wasn't in the room. Name the tension explicitly — if
there wasn't one, this probably didn't need an ADR.

## Decision

What was chosen, in active voice and present tense: "The core never imports an agent
framework." State the rule crisply enough that a reviewer can hold a pull request
against it. Include the boundaries — what the decision does *not* cover is often what
gets misread later.

## Consequences

What this makes easy, what it makes hard, and what it forecloses. Be honest about the
costs; an ADR that lists only benefits is marketing, and the next person to revisit
this decision needs to know what it actually cost. Note any obligations it creates
(conformance tests, review gates, recurring reviews).

## Notes

Optional. Implementation pointers, links to the relevant conformance suite, or
observations that don't belong in the record proper.

---

*Guidance for authors (delete this section in real ADRs).*

- **One decision per record.** If you're using "and also" to join two rules, write two
  ADRs.
- **Records are append-only.** To change a decision, write a new ADR that supersedes
  this one and update this file's status line to point at it. Never edit the Decision
  section of an Accepted ADR to say something different.
- **Amend the constitution in the same change** if this decision underlies one of its
  principles.
- **Numbering** is zero-padded four digits, assigned sequentially, never reused.
- **Prose, not bullets**, in Context and Consequences. The reasoning is the value; a
  bulleted list of assertions loses it.
