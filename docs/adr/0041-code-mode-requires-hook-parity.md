# ADR-0041: Code mode ships only with verified per-call hook parity

- **Status**: Accepted
- **Date**: 2026-07-21
- **Relates to**: [ADR-0006](0006-in-process-fail-closed-enforcement.md), [ADR-0019](0019-adapter-on-framework-capabilities.md), [ADR-0040](0040-deferred-tool-disclosure.md)
- **Requirements**: R7

## Context

Code mode — letting the model write code that calls tools, executed in a sandbox, rather
than emitting one structured tool call at a time — is a significant efficiency gain. A loop
over twenty resources becomes a few lines instead of twenty round trips, and context cost
drops accordingly.

The sandbox is genuinely secure: it constrains what executing code can reach, and that
constraint is well-engineered. The temptation is to treat that as sufficient, and it is
precisely the wrong inference.

**Sandbox safety and preserved governance are different properties.** A sandbox guarantees
that code cannot escape its execution environment. It says nothing about whether each tool
call issued from inside that code round-trips through the hook pipeline — identity
injection, risk classification, policy evaluation, redaction, audit. Code that calls twenty
tools safely, without those calls being individually intercepted, has produced twenty
ungoverned actions inside a secure box.

[ADR-0006](0006-in-process-fail-closed-enforcement.md) makes interception unconditional.
The mandated requirement it implements is not qualified by execution mode, and efficiency is
not an exception clause.

## Decision

**Code mode is adoptable in the governed path only with verified per-call hook parity.**

The verification is a **hard gate**, not a milestone note: if it cannot be independently
demonstrated that **every** tool call issued from sandboxed code round-trips through the
full hook pipeline — identity, risk class, policy, redaction, audit — then **code mode does
not ship in the governed path**, regardless of its context-efficiency advantage, and packs
continue on schema-based calling.

The requirement is unconditional. There is no profile in which the efficiency argument
outweighs it.

## Consequences

The efficiency gain is available if and only if it is genuinely free of governance cost,
which is the correct ordering — and stating it as a gate rather than an intention prevents
the outcome where a feature ships "pending verification" and the verification never
happens.

It also establishes a reusable pattern for future execution modes. Any mechanism that
changes how tool calls are issued faces the same test, and the answer is already written
down rather than relitigated under schedule pressure.

The costs are direct. Verification is real engineering work, and until it is done the
platform runs less efficiently than it could — a visible, ongoing cost with an argument
behind it that will be made repeatedly.

There is also a possibility this decision must accept: the parity may prove
undemonstrable within the framework's current design, in which case code mode simply does
not ship here. That is an acceptable outcome. A governance platform that adopts an
unverifiable execution mode for efficiency has traded away the thing it exists to provide.
