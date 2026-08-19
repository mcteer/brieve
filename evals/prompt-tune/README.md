# Prompt-tune (049)

Offline GEPA then DSPy for pack phase `AGENTS.md` files. **Eval-lane only** (ADR-0071).
Served `src/core`, `src/adapters`, and `src/surfaces` never import `dspy`.

```bash
uv sync --extra prompt-tune
python evals/prompt-tune/gepa_phase.py --pack terraform --phase write --instruction-file packs/terraform/agents/write/AGENTS.md
python evals/prompt-tune/dspy_build.py --pack terraform
```

A losing individual GEPA metric or a losing joint `build_agents` metric copies **zero**
files into `packs/`. Candidates land under `evals/prompt-tune/candidates/` and are never
executed. `promote_phase_agents` is the only path that copies the whole set into `packs/`
and updates `[[agents]]`.

Missing extra: both scripts and `promote_phase_agents` refuse `refinement_unavailable`.

## Named runner — SC-006 / E2 / E3

**Named runner: Dan McTeer.** These rows are not pytest-on-model-wording. Skip-green is a
failure of this guide.

| Field | Value |
| --- | --- |
| n | *(record here after the live run)* |
| Generic-steer pass rate on `evals/authoring` | *(record)* |
| Promoted pass rate on `evals/authoring` | *(record)* |
| Delta | **must be strictly positive** |

A non-positive delta is a failed eval. Record n, both rates, and the positive delta in this
table when the named runner completes E3. E1: connected, restricted, and air-gapped
profiles execute the same pinned files (no public-web fetch at phase start).
