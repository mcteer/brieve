# Quickstart: 046 — useful Ask answers

Validation cheapest-first. Shapes in [data-model.md](./data-model.md); rows in
[contracts/conformance-answer-usefulness.md](./contracts/conformance-answer-usefulness.md).

## Prerequisites

- `uv sync --extra adapters --extra surfaces --extra portal`
- For live legs: enclave up, `ASK_MODEL` / `RELEVANCE_MODEL` set, real
  `model-credentials/anthropic` (not the placeholder)

## 1. Hermetic gates

```sh
make check
make evals
```

Expected: existing answering suites green; new `answer_sufficiency` loaded for packs that
ship it; U1–U3 style failures prove the suite can fail (hand-run a omitting fixture if needed).

## 2. Shape and parity

```sh
uv run --extra adapters --extra surfaces --extra portal \
  pytest tests/conformance/answering tests/conformance/mcp -k 'ask or answering or parity' -q
```

Expected: answered guidance JSON has `primary_answer` + `citations`; API/MCP match; never-acts
still holds.

## 3. Portal render

With the stack up (`deploy/local/stack.sh up` or equivalent):

1. Sign in at https://127.0.0.1:8082/
2. Ask a covered guidance question (not estate).
3. Confirm the page shows a **primary answer** first, then supporting sources — not only a
   list of one-sentence claims.
4. Ask for an illustrative template the corpus supports; confirm fenced code appears in the
   primary answer when sections allow it.
5. Reopen an **old** conversation (pre-046 outcome with `claims[]` only) and confirm it still
   renders.

## 4. Sufficiency failure (SC-003)

Drive a recorded candidate that is true, cited, on-subject, and omits a `must_contain` fact
through the product path. The `answer_sufficiency` suite **must fail** that case.

## 5. Live bars (named runner: Dan McTeer)

```sh
# SC-001 — three covered guidance questions; restate substance without opening citations (3/3)
# SC-002 — fact inclusion when the fact is in offered material (≥9/10)
# SC-004 — illustrative code ask
# FR-010 — record whether the fact-bearing section was offered for the retention-shaped question
```

If FR-010 shows the fact section was never offered, **stop** and open a retrieval follow-on;
do not claim the ROADMAP usefulness case closed by presentation alone. Record SC-001 and
FR-010 outcomes in notes at the bottom of this file when run.

## 6. Explicit non-regressions

- Relevance adapter instruction still judges subject, not sufficiency.
- Estate ask UX unchanged.
- No authoring side effects from Ask.
