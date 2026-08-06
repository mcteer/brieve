# Quickstart: A model says what to do, not only what to use

**Feature**: 040 | **Date**: 2026-08-06

How to prove each layer, and — for the rows most likely to be quietly wrong — how to prove they
can **fail**. Every scenario has a row behind it; see [contracts/](contracts/).

## Prerequisites

- `uv sync --extra adapters --extra surfaces`
- Scenarios A–E run hermetically. **Scenario F needs the enclave** (`make dev-up`).
- **Run the rows where they block merges.** `make check` does **not** collect
  `tests/conformance/` — a green `make check` says nothing about any row below.

## Scenario A — The act is the model's

```sh
uv run --extra adapters --extra surfaces pytest tests/conformance/choice -q -k "arguments"
```

Expected: M1–M3 pass. Two recordings naming different targets produce two different acts; a
denied capability refuses identically regardless of who supplied the arguments; a no-argument
capability's records are byte-identical to before.

**Worth reading rather than only running: M1.** It drives *two* runs, because one act matching
one request is indistinguishable from a constant that happens to match.

## Scenario B — Resume, against both stores

```sh
uv run --extra adapters --extra surfaces pytest tests/component -q -k "revive or resume" \
  && uv run pytest tests/conformance/durability -q
```

Expected: M7, M8, M12 pass — the revived step re-invokes with the model's request, consults no
model, and a pre-feature (NULL-argument) record revives with the legacy values its first attempt
actually used.

**Prove M7 can fail.** Revert the `arguments` field on the record type and re-run: the Postgres
leg must fail with an empty request. Then note the in-memory leg **passes anyway** — it stores
the record object, so the field rides for free. That asymmetry is why the row is parameterised
over both providers, and a version of this feature proven against one store has not been proven.

## Scenario C — The one durable home

```sh
uv run --extra adapters --extra surfaces pytest tests/conformance/choice -q -k "leak or retention or removal"
```

Expected: M9–M11 pass. The request is recoverable from `intents` and from nothing else;
`TOOL_CHOSEN` still carries exactly six keys; `PRE_DECISION` still carries hashes; clearing a
**closed** bracket's request changes nothing; nothing expires what is kept.

**The retention statement an operator should read**: the request is kept **until something
removes it** — the platform expires nothing on its own. A future retention policy may clear
requests of *finished* acts only; clearing an open bracket's request would make its revival
re-invoke with nothing, which is the defect this feature exists to fix.

## Scenario D — Getting it wrong

```sh
uv run --extra adapters --extra surfaces pytest tests/conformance/choice -q -k "malformed or oversize or three"
```

Expected: M4–M6 and M17 pass. A malformed answer re-asks and exhaustion ends the run; an
oversized request refuses with its byte count and none of its content; a raised bound accepts
what the default refuses — same request to both; malformed / refused / failed are three
distinguishable records.

**Prove the bound is a bound.** Change M4's fixture to keep answering malformed objects past the
re-choice bound: the run must end, not act on the last answer.

## Scenario E — Nothing that worked moves

```sh
uv run --extra adapters --extra surfaces pytest tests/conformance/choice tests/conformance/durability tests/conformance/reports -q
```

Expected: the four recording-driven suites pass **unedited**, and M13/M14 beside them —
`"plan,apply,-"` still parses to exactly three bare choices, and a `[`-prefixed recording carries
structured choices with the same `-` terminal sentinel.

**Check the diff, not only the run**: if any of the four suites was edited to get here, FR-010
has already been violated — the blast radius arrived through the test tree instead of the code.

## Scenario F — In the environment where dispatched work actually happens

```sh
make dev-up
# dispatch a run whose recording carries a structured choice; read the trail
```

Expected: M18 — the act happened **in the allocation**, against the model-named target, with the
recording travelling the real path (Nomad meta → environment → chooser). Every other scenario
could pass while this one was false, which is the state two prior features shipped in.

## Scenario G — The guard

```sh
uv run pytest tests/unit -q -k capability
```

Expected: M16 — every capability the platform defines is registered or deliberately not, with
`run_program` citing ADR-0065 and the authoring trio citing its successor feature. The companion
row removes a ledger entry in-memory and asserts the check **fails** — a guard that cannot lose
is the defect it guards against.
