# Quickstart: 028 — the portal learns to ask

Validation in the order that finds problems cheapest. Shapes in
[data-model.md](./data-model.md); rows in [contracts/conformance.md](./contracts/conformance.md).

## Prerequisites

- `uv sync --extra adapters --extra surfaces --extra portal` — no new dependency (Principle VI;
  a new one would itself be a finding).
- The hermetic lanes need **no** enclave, no credential, no model.

## 1. The hermetic gates (run constantly)

```sh
make check      # component rows: four shapes, patience, token relay, no-classification
```

Expected highlights:

- **Refusals render the API's words** — the refusal block contains the transported `detail`
  verbatim and no portal-authored cause vocabulary (the no-classification row).
- **`/ask` carries its own patience; `/threads` in the same session carries the default** — both
  halves of SC-004, observed at the transport.
- **Estate references render with zero anchors; guidance citations with one each.**
- **A signed-out or empty-question ask costs zero API calls.**

## 2. Containment (unchanged rows, new route passing them)

```sh
uv run --extra adapters --extra surfaces --extra portal \
  pytest tests/conformance/portal -q
```

Expected: the existing rows pass **unmodified** — only `relay.py` reaches the network, every
request is a catalogued operation (`/ask` is one), the portal holds no credential, the served
client stays inside its size bound.

## 3. Accessibility (the browser lane CI runs)

```sh
uv run --extra adapters --extra surfaces --extra portal \
  pytest tests/a11y -q
```

Expected: the ask form (with expectation text), answered pages for both sources, a declined page
and a refused page pass WCAG 2.2 AA and the keyboard row.

## 4. The demonstration (SC-001) — named runner: Dan McTeer

Everything this needs has stood since 2026-08-02: the enclave, `ASK_MODEL` on the surfaces, the
credential at `model-credentials/anthropic`, and the earned `ask` cell bound.

1. `bash infra/bin/portal-up`, sign in through the browser.
2. Open **Ask**, ask *"How does an AI agent obtain an identity with Vault?"*, leave the page open.
3. Read the answer: every claim cited, every citation followable.
4. Read the trail: the `ask_answered` record carries **your** `subject_user_id`, the authorising
   cell, and `model_authority` with the credential's current generation — indistinguishable in
   kind from the 2026-08-02 MCP demonstration's record.
5. Ask about the estate (*"Which runs were denied today?"*): references render as identifiers,
   not links.

This closes the deferral 024 recorded by name: the person the portal exists for can now ask.
