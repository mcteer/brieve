# Contract: GEPA then DSPy (extra `prompt-tune`)

**Feature**: `specs/049-phase-product-prompts` | **Date**: 2026-08-19

## Extra

`pyproject.toml` optional extra **`prompt-tune`**:

```text
prompt-tune = [
  "harness[evals]",
  "dspy==3.3.0",
]
```

Install the PyPI package **`dspy`**, not the `dspy-ai` alias. License: MIT. Transitives
must pass `scripts/check-licenses.sh`. A refused license stops the extra.

Served installs (`adapters`, `surfaces`) do **not** include `prompt-tune`.

## Named methods (no substitutes)

| Pass | Method | Artifact | Metric |
| --- | --- | --- | --- |
| Individual | **`dspy.GEPA`** on a one-predictor module | one `AGENTS.md` | `phase_agents` |
| Joint | **DSPy** `dspy.Module` with five predictors, compiled with **`dspy.GEPA`** | the five-file set | `build_agents` |

MIPROv2, COPRO, or "equivalent" optimizers are out of contract.

## Named scripts

```text
evals/prompt-tune/gepa_phase.py
evals/prompt-tune/dspy_build.py
```

Candidates write under `evals/prompt-tune/candidates/`. They are not executed by
authoring-tier until `promote_phase_agents` copies them into `packs/<pack>/agents/` and
updates `[[agents]]` digests.

## Promotion helper (named)

`core.evals.promotion.promote_phase_agents(...)`

Refuses with:

| `reason_code` | When |
| --- | --- |
| `digest_mismatch` | bytes ≠ recorded digest |
| `injection_suspected` | injection lens findings |
| `promotion_incomplete` | missing `phase_agents` or `build_agents` in `suites_passed` |
| `agents_provenance_missing` | no provenance sibling |
| `refinement_unavailable` | `dspy` cannot be imported when the promotion CLI requires the extra |

Missing extra must not silently skip refinement and stamp the seed files promoted.

## Import graph

`src/core/**`, served `src/adapters/**`, and `src/surfaces/**` MUST NOT import `dspy` or
`gepa`. A unit/conformance gate fails the change if they do.

## Model access

Refinement uses the existing eval-lane model broker (ADR-0058). No new standing credential.
Not a served egress class (ADR-0071).

## Tests vs evals

Hermetic tests never call `dspy.GEPA` against a live model. Fixture cases prove the
measures can fail. Live GEPA/DSPy and SC-006 are named-runner eval work.
