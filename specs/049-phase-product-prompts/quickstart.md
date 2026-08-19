# Quickstart: Product-and-phase Build instructions

**Feature**: `specs/049-phase-product-prompts` | **Date**: 2026-08-19

Validation after implement, not the implementation. Named helpers and paths are in
[contracts/pack-agents.md](contracts/pack-agents.md) and
[contracts/prompt-tune.md](contracts/prompt-tune.md). Entities are in
[data-model.md](data-model.md).

## Prerequisites

- Repo root, `uv sync` (served extras as today). Do **not** need `prompt-tune` to prove
  binding and fail-closed.
- Packs on disk at `packs/terraform` and `packs/vault`.
- Hermetic tests: no live model (`docs/development/testing.md`).

## 1 — Pins load

```bash
make check
```

Expect: both authoring packs load; each has five `[[agents]]` rows; digests match
`packs/<pack>/agents/<phase>/AGENTS.md`.

Break it: change one byte of Terraform Write without updating `digest` → load refuses
`digest_mismatch`.

## 2 — Product isolation

Run the conformance rows in
[contracts/conformance-phase-product-prompts.md](contracts/conformance-phase-product-prompts.md)
A2–A3.

Expect: a terraform-bound fake run records `terraform/agents/research` and never
`vault/agents/research`. Vault research text is not a rename of Terraform research.

## 3 — Fail closed

Omit `packs/terraform/agents/write/AGENTS.md` (or empty it) in a fixture pack.

Expect: Write → `FAILED`, Propose never active, no `open_proposal`. Planting repository-root
`AGENTS.md` or a `SKILL.md` does not recover.

Ambiguous `RUN_PACKS=terraform,vault` → `pack_ambiguous`, not a merged prompt.

## 4 — Ask unchanged

Drive the answering path with both packs present.

Expect: `ChoiceRequest.instruction` is empty; no `packs/*/agents/` read on Ask.

## 5 — Promotion refuses an incomplete eval

Call `promote_phase_agents` with only `phase_agents` in `suites_passed`.

Expect: `promotion_incomplete`. Fixture suites include at least one failing case each
(A11).

## 6 — Extra is off the served path

```bash
# served extras only — must not import dspy
python -c "import core, adapters, surfaces"
```

Expect: the import-graph gate passes. `uv sync --extra prompt-tune` is for the named-runner
promotion CLI only. Missing extra → `refinement_unavailable`, not a silent promote.

## 7 — Named-runner eval (not merge-blocking pytest)

With eval broker and `prompt-tune`:

1. `evals/prompt-tune/gepa_phase.py` per file (GEPA). A losing metric must not promote.
2. `evals/prompt-tune/dspy_build.py` for the five-predictor program. A losing joint metric
   must not promote the set.
3. SC-006 comparison vs the generic pre-feature steer on the authoring corpus.

**Named runner**: Dan McTeer. Skip-green is a failure of this guide.
