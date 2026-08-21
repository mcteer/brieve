# Prompt-tune (049)

Offline GEPA then DSPy for pack phase `AGENTS.md` files. **Eval-lane only** (ADR-0071).
Served `src/core`, `src/adapters`, and `src/surfaces` never import `dspy`.

In plain terms: each `AGENTS.md` is the instruction card for one step of a Build
(research, plan, write, judge, propose). GEPA asks Sonnet 5 to rewrite each card so it
scores better on the phase measure. Then a second pass looks at all five cards together
and rewrites them as a set. If either pass scores *worse* than the seed cards, nothing
is copied into `packs/`.

**Terraform Write is a different measure.** Research/plan/judge/propose still score
phase-boundary needles. Terraform Write authors against all five `evals/authoring`
golden tasks (each with its subject). The metric is the two SC-006 gates —
`terraform validate` on the merged tree, property detector on the authored files.
Empty artefact scores 0 unless the task is `existing_integration_is_not_duplicated`.
HashiCorp `~>` is a pin; `>=` / `*` are not. FILE-block protocol lives on the *task*,
not in `AGENTS.md`, so a rewrite cannot promote eval-lane formatting into production
Write.

Do not run `dspy_build.py --live` against a Write card that just won on authoring
gates: the joint metric is still needles, and it will pull Write back toward slogans.

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
| Pin oracle | HashiCorp `~>` is a pin. `>=` / `*` remain floating. Shots after this change are not comparable to the 20 Aug `~>`-as-floating runs without noting the detector. |
| Generic steer (21 Aug, after pin oracle) | tooling **4/5**, reference **1/5** (`static_credential_lookalike`). `pin_the_provider` still floated. `existing_integration_is_not_duplicated` duplicated the subject. |
| Seed Write card (shipped `packs/…/write/AGENTS.md`, same day) | tooling **4/5**, reference **0/5**. Empty on both secret-store tasks; duplicated the existing integration; pin still missing. |
| Write GEPA (authoring gates, `--max-full-evals 10`) | seed **0.5** → compiled **0.9** on the five-task scalar (0.5 per gate; empty-when-needed is 0). Candidate: `evals/prompt-tune/candidates/terraform/write/AGENTS.md`. |
| GEPA card on SC-006 | tooling **5/5**, reference **4/5**. Miss: `least_privilege_role` still has a wildcard. Both-gates-complete still false. |
| Delta vs generic | reference **+3/5** (20% → 80%). Tooling **+1/5**. Strictly higher reference pass rate. |
| Promoted? | **No.** `promote_phase_agents` is whole-set; only Write was compiled. The candidate also bakes eval-lane `--- FILE` protocol into the card and is truncated mid-sentence — not production `author_file` bytes. |

A non-positive delta is a failed eval. This named-runner shot is a positive reference-gate delta and an incomplete corpus (wildcard still fails). E3 stays open until a promoted, production-shaped set beats generic at the same n and both gates can complete. E1: connected, restricted, and air-gapped profiles execute the same pinned files (no public-web fetch at phase start).
