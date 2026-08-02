# Quickstart: 025 — estate-state answering

Validation scenarios, in the order that finds problems cheapest. Contracts and shapes live in
[data-model.md](./data-model.md) and [contracts/conformance.md](./contracts/conformance.md).

## Prerequisites

- `uv sync --extra adapters --extra surfaces --extra portal` — no new extras, no new dependency.
- **No enclave and no credential for anything blocking.** Only the two named live runs need
  `.env`'s `ANTHROPIC_API_KEY`, and both have a named runner.

## 1. The hermetic gates (run constantly)

```sh
make check    # routing, scope, estate path, scorer — component and unit rows
make evals    # the reauthored estate_state scoring the product path, no vendor
```

Expected: green, and the eval gate's scorer-identity assertion names the estate scorer for
`estate_state` — the same anti-reversion row 024 added for its two suites.

## 2. The behaviour, end to end (hermetic conformance)

```sh
uv run --extra adapters --extra surfaces --extra portal \
  pytest tests/conformance/answering tests/conformance/mcp/test_ask_parity.py -q
```

Expected, by scenario:

- **Differential entitlement (SC-001)**: two subjects, same question, answers differ exactly by
  role scope — compared, not inspected.
- **Both routing directions (SC-009)**: estate-shaped never touches the corpus;
  guidance-shaped writes **no evidence-access record**.
- **Caller-indistinguishability (SC-008)**: "no records" and "not yours" — identical responses,
  different trail dispositions.
- **Never-acts (SC-004)**: instruction-shaped estate questions change nothing; the import row
  covers the new modules.
- **Parity**: estate answer, estate decline, store failure — same verdict on API and MCP.

## 3. FR-012 — name the old failure (paid, ~15 calls, BEFORE reauthoring lands)

```sh
make evals-smoke   # harness sanity first, as always
# then the one-off: old estate_state, vault, live model, per-case output printed
```

Expected: the failing case id(s) from 2026-08-01, named. Record the finding in
[contracts/conformance.md](./contracts/conformance.md) § *FR-012 finding* — either way.

## 4. Live qualification (paid, named runner)

```sh
make evals-live
```

Expected: the reauthored `estate_state` passes for both packs through the product path — the same
fixture records offered to a real model, scored by the same fidelity thresholds as the blocking
lane. **On green**: the `ask` cell's Qualified Model Matrix column may move to `live`; on red, it
stays `fixture` and the failure is recorded by case, which after FR-012 the tooling now supports.

## 5. The served process (before calling it done)

`make conformance` on the live enclave, then one real `ask` through the served MCP surface with an
estate-shaped question — the assembly is the one path no test covers. Expected: an answer whose
references resolve, an `ask_answered` record carrying `source: estate`, and an evidence-access
record one hop away.
