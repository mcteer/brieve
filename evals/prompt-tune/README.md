# Prompt-tune (049)

Offline GEPA then DSPy for pack phase `AGENTS.md` files. **Eval-lane only** (ADR-0071).
Served `src/core`, `src/adapters`, and `src/surfaces` never import `dspy`.

In plain terms: each `AGENTS.md` is the instruction card for one step of a Build
(research, plan, write, judge, propose). GEPA asks Sonnet 5 to rewrite each card so it
scores better on the phase measure. Then a second pass looks at all five cards together
and rewrites them as a set. If either pass scores *worse* than the seed cards, nothing
is copied into `packs/`.

```bash
uv sync --extra prompt-tune
# Per file. Default budget is 10 full GEPA evals (the test cap).
python evals/prompt-tune/gepa_phase.py --live --pack terraform --phase write \
  --instruction-file packs/terraform/agents/write/AGENTS.md
# Then the five-card set together (same 10-eval cap):
python evals/prompt-tune/dspy_build.py --live --from-candidates --pack terraform
```

Do **not** pass `--auto light|medium|heavy` for a test run. `auto=light` is hundreds of
metric calls per file. `--max-full-evals 10` is the default.

A losing individual GEPA metric or a losing joint `build_agents` metric copies **zero**
files into `packs/`. Candidates land under `evals/prompt-tune/candidates/` and are never
executed. `promote_phase_agents` is the only path that copies the whole set into `packs/`
and updates `[[agents]]`.

Missing extra: both scripts and `promote_phase_agents` refuse `refinement_unavailable`.

The live compile needs the eval-lane key in the environment (`EVAL_PROVIDER_API_KEY`) or
gitignored `.env` (`ANTHROPIC_API_KEY`). The model is Sonnet 5 (`anthropic/claude-sonnet@5`).

## Named runner — SC-006 / E2 / E3

**Named runner: Dan McTeer.** These rows are not pytest-on-model-wording. Skip-green is a
failure of this guide.

`make evals-authoring-live` is the TF-output lane: Sonnet 5 authors against
`evals/authoring` golden tasks; gate one is `terraform validate`; gate two is the
property detector. Optional overlay:

```bash
INSTRUCTION_FILE=packs/terraform/agents/write/AGENTS.md EVAL_LABEL=write-card \
  make evals-authoring-live
```

| Field | Value |
| --- | --- |
| n | 5 golden tasks, one shot each, Sonnet 5 (`anthropic/claude-sonnet@5`), Terraform 1.15.8 |
| Generic-steer pass rate | tooling **5/5**, reference **1/5** (`dynamic_database_secret` only). `existing_integration_is_not_duplicated` duplicated the subject. `pin_the_provider` had no version pin. |
| Write-card pass rate | tooling **5/5**, reference **1/5** (`existing_integration_is_not_duplicated` only — empty artefact). `dynamic_database_secret` over-applied "already done" and authored nothing. `pin_the_provider` still used a floating constraint. |
| Delta | **0** on reference pass rate (20% → 20%). Not strictly positive. E3 remains open. |
| GEPA/DSPy (earlier) | 10 individual + 2 joint compiles, `--max-full-evals 10`. Valset did not beat the seed; nothing promoted from that run. |

A non-positive delta is a failed eval. E3 remains open until a later run produces a strictly positive delta on `evals/authoring` at the same n. E1: connected, restricted, and air-gapped profiles execute the same pinned files (no public-web fetch at phase start).
