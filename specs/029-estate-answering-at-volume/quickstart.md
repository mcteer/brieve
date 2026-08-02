# Quickstart: 029 — estate answering at real volume

Validation in the order that finds problems cheapest. Shapes in
[data-model.md](./data-model.md); rows in [contracts/conformance.md](./contracts/conformance.md).

## Prerequisites

- `uv sync --extra adapters --extra surfaces --extra portal` — no new dependency.
- The hermetic lanes need no enclave, no credential, no model. Volume fixtures build in-memory.

## 1. The hermetic gates (run constantly)

```sh
make check
```

Expected highlights:

- **The five questions that failed on 2026-08-02 route to the estate**, and the guidance
  regression set (including *"How do I read a secret?"*) stays guidance.
- **The volume row**: at the live tenant's measured skew (hundreds of step records against tens of
  run records), a runs question is answered from predominantly run records.
- **`limit_per_type=None` is byte-for-byte today's read** — every pre-existing row passes
  untouched.
- **Focus only narrows**: always a subset of the visible set; empty intersection falls back to
  visible; empty visible still refuses before any read.

## 2. The conformance sweep (hermetic half)

```sh
uv run --extra adapters --extra surfaces --extra portal \
  pytest tests/conformance --ignore=tests/conformance/durability -m "not enclave and not live_model" -q
```

Expected: the answering rows including the window note (present when truncated, absent when not,
on both surfaces), and the portal rows rendering it.

## 3. The enclave lane

```sh
make conformance
```

Expected: the per-type property rows against the real Postgres with seeded thousands — the half of
FR-008 a hermetic lane cannot honestly claim.

## 4. The mutation check (at implement, recorded in the contract)

Flip the window selection in one implementation only; the parametrized rows must fail. This is the
discipline that would have caught finding three, applied before the rows are trusted.

## 5. SC-007 against the live tenant — named runner: Dan McTeer

Through the deployed portal (everything stands from 028's demonstration):

1. Ask each of: *"Which tools were used?"*, *"What did the planner agent do?"*, *"Were any secrets
   read?"*, *"Which agents are active?"*, *"What ran today?"*
2. Each reaches the estate and answers against 236k entries; answers about runs cite run records.
3. Where a type truncated, the answer says what it rests on — *"Based on the 200 most recent run
   records of 1,847 today."*
4. *"Which runs were denied?"* still declines for an operator — correct under FR-009, recorded,
   and unchanged until the visibility decision is taken.
