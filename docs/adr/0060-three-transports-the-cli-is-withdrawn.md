# ADR-0060: Three transports — the CLI is withdrawn

- **Status**: Accepted
- **Date**: 2026-08-05
- **Supersedes**: the transport enumeration and the CLI device-grant clause of [ADR-0033](0033-four-transports-one-authorization-core.md)
- **Relates to**: [ADR-0034](0034-conversational-web-ui.md), [ADR-0047](0047-conformance-gate-rows-attach-as-features-land.md)
- **Requirements**: R15

## Context

[ADR-0033](0033-four-transports-one-authorization-core.md) enumerated four northbound
transports — tool server, API, CLI, and portal — and the constitution restated that count as
a normative clause: *"Northbound: exactly four transports — MCP, API, CLI, portal."* Three of
them were built. 008 shipped the API, 009 shipped MCP, 012 shipped the portal. The CLI was
never started.

On 2026-07-28 it was tabled, and the tabling was careful about what it was: a scheduling
decision, not a design one. `ROADMAP.md` recorded that API, MCP, and the portal cover
substantially every persona, that a CLI would be a fourth route to the same operations for an
audience two of the three already serve, and that nothing was being superseded — *"If a demand
appears that the other three genuinely cannot meet, ADR-0033 still describes how a CLI would
work, down to the device authorization grant it would use."*

The tabling was eight days ago, so nothing about elapsed time argues this either way, and
this record does not pretend otherwise. What changed is not the demand picture but the
maintainer's intent: the platform is not going to build a CLI, and holding a place for one
has a cost that the tabling explicitly acknowledged and accepted. That cost is the tension
this record resolves. The constitution is the document every specification is analyzed against. When it
says the platform has four transports and the platform has three, the discrepancy is not
cosmetic: it is the same failure mode [ADR-0047](0047-conformance-gate-rows-attach-as-features-land.md)
identified in tests, one level up. A stub that passes asserts a property nothing holds; a
constitutional clause naming a surface nobody built asserts a shape the platform does not
have. Both are worse than the honest absence, because both are load-bearing for a reader who
has no way to check.

The parity gate had already been amended around the gap rather than through it. Constitution
v1.2.0 changed *"surface parity across all four transports"* to *"across every pair of
implemented transports"* — recorded then as **a correction, not a policy change**, because
ADR-0033 had only ever said *"any transport"*. That amendment fixed the gate. It left the
count.

## Decision

**Three northbound transports — MCP, API, and portal — as clients of one authorization
core.** The CLI is withdrawn, not tabled: it is no longer a surface this platform intends to
build, and no document may describe the platform as having one.

The CLI's authentication flow goes with it. ADR-0033 specified a device authorization grant
for the CLI, and that clause now has no subject; it is withdrawn rather than left standing as
guidance for a surface that is not coming. Human authentication remains authorization code
with PKCE for the portal and OAuth 2.1 for the tool server, unchanged.

**What this record does not touch, stated because the enumeration is the smallest part of
ADR-0033.** One authorization core, with every transport a client of it, stands. Parity as a
*conformance-asserted test* rather than an intention stands. Human authentication always
against the organization's own identity provider stands. No static API keys, on any surface,
ever — stands. Those are the decision ADR-0033 was actually making; four was the inventory it
happened to have at the time.

**Three is a ceiling, not a floor.** Adding a fourth transport requires a new ADR, which is
the property the original enumeration existed to protect — a surface may not appear by
someone deciding one afternoon that the platform needs one. Withdrawing the CLI narrows the
number; it does not loosen the gate on the number.

## Consequences

The parity gate gets stronger by getting smaller. It binds across every pair of implemented
transports, and with three implemented that is three pairs, all of them real. Under the
previous count the gate was measured against an inventory of four, one of which could never
fail because it could never run — so the fourth's absence read as coverage not yet reached
rather than coverage that was never coming.

The constitution stops describing a platform other than this one. This is the whole point,
and it is worth naming plainly: every `/speckit.analyze` pass measures a specification against
that document, so a clause naming a nonexistent surface is a false premise sitting upstream of
every future feature's analysis.

**What this costs.** People who live in a terminal now reach this platform through the API,
which means writing a client or using `curl` rather than being handed one. That is a real
ergonomic loss and it is the reason the CLI was tabled rather than declined the first time.
It is accepted here for the reason the tabling gave — the three built surfaces cover
substantially every persona — with the difference that the platform now says so outright
rather than leaving a placeholder that reads like a commitment.

**What it forecloses.** ADR-0033's device-grant specification stops being live guidance. A
future CLI would need to decide its authentication flow again rather than inheriting one, and
that is correct: a flow chosen in 2026-06 for a surface never built is not a decision that
should bind whoever eventually needs one.

**Obligation.** This record amends the constitution in the same change, per the ADR authoring
rule that a decision underlying a principle amends it together. ADR-0033 is **not** edited —
records are append-only, and its Decision section still says what was decided in 2026-06. Its
status line points here.

## Notes

Propagated in the same change: `.specify/memory/constitution.md` (Principle II's transport
clause, with a Sync Impact Report), `docs/glossary.md` (the effective-authority surface list),
`docs/adr/0033-*.md` (status line only), `ROADMAP.md` (Tabled → Withdrawn, in both the
transport table and the demand-gated backlog), and the `src/surfaces/` package docstrings that
restate the count.

Historical documents are left alone. `specs/008`, `specs/009`, and `specs/012` describe a
four-transport platform because that is what was true when they were written, and rewriting
them would destroy the record of how the platform got here for the sake of a tidier grep.
