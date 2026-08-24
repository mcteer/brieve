# Prompt-tune (049)

Offline GEPA then DSPy for pack phase `AGENTS.md` files. **Eval-lane only** (ADR-0071).
Served `src/core`, `src/adapters`, and `src/surfaces` never import `dspy`.

In plain terms: each `AGENTS.md` is the instruction card for one step of a Build
(research, plan, write, judge, propose). GEPA asks Sonnet 5 to rewrite each card so it
scores better on the phase measure. Then a second pass looks at all five cards together
and rewrites them as a set. If either pass scores *worse* than the seed cards, nothing
is copied into `packs/`.

**Terraform Write is a different measure.** Research/plan/judge/propose score
phase-boundary behavior on all five `evals/authoring` golden prompts (plus one
write-now fail case): keyword coverage, no HCL/`--- FILE` bodies, judge must
emit `allow=true` or `deny`, propose must describe a pull request. Terraform
Write authors against all five golden tasks (each with its subject). The metric
is the two SC-006 gates — `terraform validate` on the merged tree, property
detector on the authored files. Empty artefact scores 0 unless the task is
`existing_integration_is_not_duplicated`. HashiCorp `~>` is a pin; `>=` / `*`
are not. FILE-block protocol lives on the *task*, not in `AGENTS.md`, so a
rewrite cannot promote eval-lane formatting into production Write.

Do not run `dspy_build.py --live` against a Write card that just won on authoring
gates: the joint metric is still needles, and it will pull Write back toward slogans.

```bash
uv sync --extra prompt-tune
# Per file. Default budget is 10 full GEPA evals (the test cap).
python evals/prompt-tune/gepa_phase.py --live --pack terraform --phase write \
  --instruction-file packs/terraform/agents/write/AGENTS.md
# Then the five-card set together (same 10-eval cap) — do not run this against a
# Write card that won on authoring gates; the joint metric is still needles:
# python evals/prompt-tune/dspy_build.py --live --from-candidates --pack terraform
# Production-shaped five-file copy into packs/ (terraform):
python evals/prompt-tune/promote_terraform.py
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
| GEPA card on SC-006 | tooling **5/5**, reference **4/5**. Miss: `least_privilege_role` still has a wildcard. Both-gates-complete still false. Eval-lane `--- FILE` protocol is in the card; not production `author_file`. |
| Production-shaped card (`AGENTS.production.md`, no FILE protocol, 21 Aug first shot) | tooling **4/5**, reference **5/5**. Least-privilege wildcard miss is gone. One authored tree failed `terraform validate` (task unnamed — the live lane did not print per-task tooling). |
| Diagnostic (same card, per-task tooling + dump) | tooling **3/5**, reference **4/5**. `dynamic_database_secret` and `static_credential_lookalike` failed `terraform init`: both `variables.tf` files were truncated mid-block at `max_tokens=4096`. `least_privilege_role` used a trailing `path "…/*"` glob (VALID BUT WRONG). |
| Production-shaped retry (`EVAL_LABEL=gepa-write-production-8192`) | **tooling 5/5, reference 5/5, both gates passed.** Live lane `max_tokens` is 8192 (same as Write GEPA). Card tells the cell to add the smallest leased `data "vault_generic_secret"` rather than standing up `vault_database_secret_backend_*`, and forbids path globs. All five `stop_reason=end_turn`. |
| Delta vs generic | GEPA FILE card: reference **+3/5**. Production-shaped (this 5/5 shot): reference **+4/5** vs the 21 Aug generic (20% → 100%) and tooling **+1/5** vs that generic's 4/5. Same-n generic was not re-shot on this retry. |
| Promoted? | **Yes, 24 Aug.** Terraform `[[agents]]` **0.2.0**. Production-shaped five-file set via `promote_phase_agents` (lens clean). Write is this 5/5 `AGENTS.production.md`, not the FILE GEPA card. Joint `dspy_build.py --live` was not run (joint metric is still needles). Vault is unchanged. |

A non-positive delta is a failed eval. Terraform Write vs the 21 Aug generic is reference **1/5 → 5/5** and tooling **4/5 → 5/5**. Same-n generic was not re-shot after this promotion. Vault SC-006 is still open. E1: connected, restricted, and air-gapped profiles execute the same pinned files (no public-web fetch at phase start).

The live lane now prints per-task `terraform validate` / `stop_reason`, names `TOOLING FAILED` beside `VALID BUT WRONG`, and dumps merged trees under gitignored `evals/prompt-tune/sc006-dump/<label>/`.

**Terraform Plan GEPA** (21 Aug, phase-boundary metric, `TASK_MAX_TOKENS=4096`, `--max-full-evals 10`): seed **0.717** → compiled **0.760**, `lost=false`. Candidate: `evals/prompt-tune/candidates/terraform/plan/AGENTS.md` (injection lens clean). Not promoted — whole-set rule.

**Terraform Research GEPA** (21 Aug, first shot): seed **0.765** → compiled **0.0**, `lost=true`, `injection_suspected` (`bypass_approval` + `escalate`). Seed kept. The lens ran only after GEPA finished; feedback that said "avoid escalation" taught `do not escalate` / `never skip approval`, which still fire.

**Terraform Research GEPA** (21 Aug, `lens_cap` in the metric): seed **0.647** → compiled **1.0**, `lost=false`. Candidate: `evals/prompt-tune/candidates/terraform/research/AGENTS.md` (injection lens clean). Seed is lower than the first shot because the lens now scores during GEPA.

**Terraform Judge GEPA** (21 Aug): seed **0.776** → compiled **0.853**, `lost=false`. Candidate: `evals/prompt-tune/candidates/terraform/judge/AGENTS.md` (injection lens clean).

**Terraform Propose GEPA** (21 Aug, first shot): seed **0.633** → compiled **0.0**, `lost=true`, `injection_suspected` (`escalate`). Seed kept.

**Terraform Propose GEPA** (21 Aug, `lens_cap` in the metric): seed **0.167** → compiled **0.784**, `lost=false`. Candidate: `evals/prompt-tune/candidates/terraform/propose/AGENTS.md` (injection lens clean).

| Phase | Seed | Compiled | Outcome |
| --- | --- | --- | --- |
| research | 0.647 | 1.0 | improved (lens in metric); raw GEPA was eval-homework, not shipped |
| plan | 0.717 | 0.760 | improved; production-shaped and shipped |
| write | 0.5 | 0.9 | improved (authoring gates); FILE card not shipped |
| judge | 0.776 | 0.853 | improved; raw GEPA was eval-homework, not shipped |
| propose | 0.167 | 0.784 | improved (lens in metric); raw GEPA was eval-homework, not shipped |

**Promoted 24 Aug (terraform `[[agents]]` 0.2.0).** Production-shaped five-file set in `packs/terraform/agents/` via `promote_phase_agents` (lens clean; `phase_agents` + `build_agents` attested as the mechanical pack qualifications). Write is `AGENTS.production.md` (SC-006 both gates 5/5), not the FILE GEPA card. Research / judge / propose ship seed practice plus grant-scope lines — not the GEPA “produce the guidance / grading” overlays. Plan ships GEPA practice with eval-speak stripped. Joint `dspy_build.py --live` was not run. Vault is unchanged.
