# Quickstart: validating packs and the eval gates

**Feature**: `specs/013-capability-packs` | **Date**: 2026-07-29

## Prerequisites

```bash
make dev-up && make dev-status
```

## 1 — The findings are real *(runs today)*

```bash
# F1: the entrypoint names the line packs replace
grep -A3 "capability packs, which are a" src/surfaces/dispatch/entrypoint.py

# F2: risk_class is in the glossary and nowhere in the code
grep -c "risk_class" src/core/registry/memory.py     # -> 0
grep -c "Risk class" docs/glossary.md                # -> 1

# F3: there is no approval audit event to be confused with
grep -ci "approval" src/core/audit/schema.py         # -> 0

# The read policy covers two prefixes and not the matrix (analyze pass 1, I1)
grep -c "model-matrix" infra/modules/trust-fabric/policies.tf   # -> 0 before the fix

# Tiers had nothing to bound: no workflow concept anywhere (G1)
grep -rl "workflow" src/core/ | wc -l                # -> 0 before the fix
```

## 2 — The core stays product-blind *(after packs land)*

```bash
# The row (T020) uses an explicit module allowlist, not a grep filter — `vault_fabric.py`
# and `credentials.py` mention Vault throughout because they are the TRUST FABRIC, and a
# pattern that excluded them by filename would still match their contents. Run the row
# rather than approximating it:
uv run --extra adapters --extra surfaces pytest \
  tests/conformance/packs/test_core_is_product_blind.py -q

# SC-002's second clause, shown rather than argued:
git diff --stat main -- src/core/    # adding the second pack: zero files
```

## 3 — A pack cannot grant *(the most plausible defect)*

```bash
uv run --extra adapters --extra surfaces pytest tests/component -k "pack and ceiling" -q
```

**Expect**: a pack declaring a tool outside its definition's ceiling refuses
`pack_exceeds_ceiling`. This is the row that matters most — a pack that grants reads as the
pack system working.

## 4 — The matrix refuses *(the blocking half of Principle VIII)*

```bash
uv run --extra adapters --extra surfaces pytest tests/component -k matrix -q
```

**Expect**: an unqualified cell refused at definition time naming the cell; a withdrawn cell
refused at run start; fallback only to a qualified cell, recorded; no qualified cell means
the run stops with its reason.

## 4b — The structural rows *(after packs land)*

```bash
uv run --extra adapters --extra surfaces pytest tests/conformance/packs -q
```

**Expect**: containment, tool vocabulary, no-bypass, no-widening, no-auto-tracking, and the
run-path layering row. **These do not run under `pytest tests/component`** — `testpaths`
covers `tests/unit` and `tests/component` only, so a reader who runs the sections above and
stops has exercised none of them. `make conformance` includes this directory (wired at
T012b).

## 5 — The gates *(fixtures)*

```bash
make evals
```

**Expect**: four suites green against fixtures. Report fidelity absent, with its ADR-0018
skip visible in the output rather than silent.

## 6 — The gates *(live model — named runner)*

```bash
export EVAL_PROVIDER_KEY=...     # the name is defined in src/core/evals/scoring.py and
                                 # asserted by T045 against that constant, not a literal.
                                 # Dev-lane only: never in a jobspec, never read by a run.
make evals-live
```

**Expect**: the same suites, scored against a real model. Record each cell's outcome in
`contracts/conformance-packs.md`. **A cell qualified only by the fixture lane is qualified
against a recording**, and the table is where that stops being invisible.

## 7 — The judge chain terminates

```bash
uv run --extra adapters --extra surfaces pytest tests/component -k judge -q
```

**Expect**: the first judge qualified against `evals/seed/`; every later judge by a judge
already qualified; a judge pointed at itself refused rather than closing the loop.

## What a passing run does NOT prove

- **Terraform's tools work.** Terraform is not in the enclave; that pack's tool layer is
  fixture-backed, and the tool half is what Principle II governs.
- **A fixture-qualified cell is a qualified model.** It is a qualified *recording*.
- **Report fidelity.** Owed against ADR-0018, which is unbuilt.
- **That the gates would catch anything if their fixtures vanished.** A green run proves
  the suites passed, not that an unrunnable suite fails — that is its own row (T040a), with
  its own positive control, and it is the property that stops a broken gate reading green.
- **The injection lens catches novel phrasing.** It is pattern-based by necessity — a
  model-scored lens would need a qualified cell, which needs the gates, which is a second
  regress with no seed set to terminate it. The lens is a floor; ADR-0004's human review
  covers the rest.
