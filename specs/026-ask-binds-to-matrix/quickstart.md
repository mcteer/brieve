# Quickstart: 026 — asking binds to the Qualified Model Matrix

Validation scenarios, cheapest first. Shapes and rows live in [data-model.md](./data-model.md) and
[contracts/conformance.md](./contracts/conformance.md).

## Prerequisites

- `uv sync --extra adapters --extra surfaces --extra portal` — no new dependency.
- **Nothing blocking needs a credential or the enclave.** Only §4 touches the enclave, and it
  joins an existing lane.

## 1. The hermetic gates (run constantly)

```sh
make check    # parsing, resolution, dispositions, ordering — component and unit rows
make evals    # unchanged suites still green — this feature changes no gate
```

## 2. The refusal, end to end (hermetic conformance)

```sh
uv run --extra adapters --extra surfaces --extra portal \
  pytest tests/conformance/answering tests/conformance/mcp/test_ask_parity.py -q
```

Expected, by scenario:

- **Provider never called (SC-001)**: no qualified cell → the provider's own call count is zero,
  both surfaces, both sources.
- **Fixture default refuses (SC-003b)**: a provider injected with no authority refuses `unbound` —
  the harness does not auto-qualify.
- **Per-source (SC-003a)**: guidance bound + estate unbound → guidance answers, estate refuses,
  same session.
- **Distinguishable refusals (SC-004)**: `unbound` / `unqualified_cell` / `matrix_unreadable`,
  each recorded (SC-008), identical on both surfaces (SC-007).
- **Substitution (SC-006)**: pinned model unavailable + qualified alternative → answer produced,
  record carries `bound_cell` ≠ `cell` and the reason; no alternative → refusal, never an
  unqualified model.

## 3. The tripwire (SC-009)

Comment out the resolution step in the surface; the provider-never-called row fails by counting a
call. Restore it. This is the row 024's contract asserted without having.

## 4. The enclave lane

`make conformance` — the binding-readability row (identity lane) asserts the surface's role can
read `data/ask-bindings` and `data/model-matrix` against the live fabric, on the
`test_matrix_is_readable` pattern. No new named runner.

## 5. The served process (before calling it done)

**Credential-free by design** (analysis U1) — the served surface holds no vendor key, so the check
proves resolution by how the refusal *moves*:

1. Enclave up, nothing seeded → an ask refuses **`unbound`**.
2. Seed the binding and its two cells (T022) → the same ask now refuses
   **`provider_unavailable`** — which can only happen if governance resolution **passed**.
3. Withdraw a cell in the matrix record → **`unqualified_cell`**, provider never in the picture.

Each step's disposition lands in the `ask_answered` record. A real served *answer* would need a
vendor credential inside the service — an undecided deployment posture, recorded as deferred.
