# Quickstart: Deferred disclosure and code mode

**Feature**: 036 | **Date**: 2026-08-05

How to prove the feature works, end to end, without reading the suites. Every scenario
here has a conformance row behind it — this guide is the human-walkable version, per
[contracts/](contracts/).

## Prerequisites

- `uv sync --extra adapters --extra surfaces --extra sandbox` — the `sandbox` extra
  carries `pydantic-monty` (exact pin; note the PyPI name — plain `monty` is an unrelated
  materials-science package and installing it is not an error anyone reports).
- No enclave, no live model, no network: every scenario runs on scripted models against
  the adapter fixtures (`tests/harness/adapter_fixtures.py`).

## Scenario A — Parity: disclosure changes nothing governance can see

```sh
uv run --extra adapters --extra surfaces pytest tests/conformance/adapter -q -k disclosure
```

Expected: the parity rows (D1–D2) pass — one operation, two postures, identical
decisions, identical records between `PRE_DECISION` and `POST_DECISION`. D4 prints the
measured schema-material ratio in its output; the deferred figure is ≤ 25% of eager.

## Scenario B — Discovery is in the trail, and is not a decision

Run any deferred-posture component test with `-s` and read the captured audit:

```sh
uv run --extra adapters --extra surfaces pytest tests/component -q -k discovery
```

Expected: `DISCOVERY_OBSERVED` events carrying queries and matches (including an empty
match), **no** `PRE_DECISION` for any search, and an event type no reader can mistake
for a tool call.

## Scenario C — Code mode: N calls, N+1 decisions, denials included

```sh
uv run --extra adapters --extra surfaces --extra sandbox pytest tests/conformance/adapter -q -k code_mode
```

Expected: C1–C4 pass — a three-call program yields four `PRE_DECISION`s; a policy-denied
call fails inside the program; `open`/`eval`/an invented name refuse as unregistered
tools on the ordinary path.

## Scenario D — The suite can lose

C5 is the row to read, not just run: it rigs a seam handler that skips `invoke_tool` and
asserts the parity assertion **fails** against it. If C5 itself fails, the parity rows
have stopped being able to detect a bypass — treat that as the emergency it is.

## Scenario E — The honest absence

```sh
uv run --extra adapters --extra surfaces pytest tests/conformance/adapter -q -k "code_mode and absent"
```

(No `sandbox` extra.) Expected: `run_program` refuses with a stated reason naming the
missing runtime — never an ImportError, never silence (C8).

## Scenario F — The cause is recoverable

After Scenario C, read the run's evidence through the governed read path (the component
test does this via the API operation, not by peeking at the store): the program text
comes back, its `program_sha256` joins it to each inner call, and the ordered decisions
reconstruct what happened and why (C9).

## What done looks like

- All rows in both contracts green; C5 green *by failing its rigged double*.
- `make check` green — including the structural gates U1–U3.
- The planning artifacts' obligations discharged: ADR-0061 merged (amending ADR-0040 by
  pointer), Principle V review recorded on the PR.
- `OWED` untouched: the parity row binds at merge, so it never enters the owed table.
