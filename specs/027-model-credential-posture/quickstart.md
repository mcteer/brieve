# Quickstart: 027 — how the platform holds a model credential

Validation in the order that finds problems cheapest. Shapes in
[data-model.md](./data-model.md); rows in [contracts/conformance.md](./contracts/conformance.md).

## Prerequisites

- `uv sync --extra adapters --extra surfaces --extra portal` — no new dependency.
- Blocking lanes need **no** credential. Only the deployed-answer and revocation checks (§4–5)
  need a real key in the store, and both have a named runner.

## 1. The hermetic gates (run constantly)

```sh
make check    # the reader, the refusal vocabulary, no-cache — component and unit rows
make evals    # unchanged; this feature changes no gate
```

## 2. The posture, hermetically (conformance)

```sh
uv run --extra adapters --extra surfaces --extra portal \
  pytest tests/conformance/answering tests/evals_live -m "not enclave and not live_model" -q
```

Expected:

- **Three refusals, three dispositions** — `credential_unavailable` ≠ `unqualified_cell` ≠
  `provider_unavailable`, in the fixed order (cell → credential → vendor).
- **No env fallback** — the row sets `EVAL_PROVIDER_API_KEY` and the production fetch still
  refuses. If this passes only because the var is unset, it is not testing anything.
- **Never persisted** — no checkpoint, log, trail entry, or context carries the value; the trail
  carries `vault:model-credentials/...@v<n>`.
- **Eval lane exempt, stated at the lane** — `client_and_model` still honours the env key, and the
  comment there names the exemption.
- **Both paths, one reader** — ask path and a non-fixture run both reach `BrokeredModelCredential`.

## 3. The two documents

```sh
git diff main -- .specify/memory/constitution.md docs/adr/0058-model-credential-brokering.md
```

Expected: constitution at **v1.4.0** with *two named exceptions* and the static-key sentence
rewritten; ADR-0058 present. **These land in this PR, not a later one** — the capability and the
amendment are one change.

## 4. The enclave

`make conformance` — the readability row asserts `mcp-surface` and the run role can read
`model-credentials/<vendor>` against the live fabric, and the constitution-agreement check fails a
deployment that contradicts the amended text.

## 5. The thing three features could not do (SC-001, SC-003) — named runner

**Three things must be true first, and the third is the one that surprises.** A real key at
`model-credentials/anthropic`; `ASK_MODEL` set on the surface (it is a jobspec variable, passed by
`mcp-surface-up` from `.env`); and **a matrix cell qualifying that model for `ask`, with the ask
binding naming it**. Governance is checked before the credential, so without the third the ask
refuses `unqualified_cell` and never reads the store — measured, not predicted. Qualifying a cell
is eval-gated work this feature deliberately does not do.

With all three:

1. Ask through the served surface → **a real answer**, and `model_authority` on the record.
2. Rotate the credential in the store → the next ask answers on the new generation (version
   increments in the reference).
3. **Delete** it → the next ask refuses `credential_unavailable`, **no restart**, the moment
   locatable in the trail.

This is the first time a person gets an answer from the deployed platform. It is also the
revocation demonstration — the same three steps prove both.
