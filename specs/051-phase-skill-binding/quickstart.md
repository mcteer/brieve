# Quickstart: Adopted skills reach the phase that needs them (051)

**Feature**: 051 | **Plan**: [plan.md](plan.md) | **Contracts**: [pack-skill-binding.md](contracts/pack-skill-binding.md)

How to prove this feature works end to end. Scenarios map to user stories; each says what to
run and what it must show. Implementation belongs in `tasks.md` — this is the validation
guide.

## Prerequisites

```bash
uv sync
```

Hermetic scenarios (1–6) need nothing else. Scenario 7 needs `make dev-up` and an eval
broker; scenario 6 needs the `prompt-tune` extra.

---

## Scenario 1 — The write model actually receives the skill (US1, FR-001)

```bash
uv run pytest tests/conformance/phase_agents/ -k "assembly or delivery" -q
```

**Expect**: `PhaseAgents.body` for `terraform` × `write` contains `AGENTS.md` in full, then
both skills between `--- BEGIN PINNED SKILL: … ---` / `--- END PINNED SKILL: … ---`
delimiters, in `[[skills]]` declaration order.

Read what a phase would receive:

```bash
uv run python -c "
from pathlib import Path
from core.packs.agents import load_phase_agents
from core.packs.loader import FilesystemPackLoader
root = Path('packs')
a = load_phase_agents('terraform', 'write', loader=FilesystemPackLoader(root), packs_root=root)
print(f'{len(a.body):,} bytes; skills: {[s.name for s in a.skills]}')
print('validation block taught:', 'error_message' in a.body)
"
```

**Expect**: roughly 16,600 bytes, both skill names in `plan`/`write`/`judge` order of
declaration, and `True` — the `validation` example is present, which is the SC-002 rule
(scenario 7).

**Then check a phase that is not bound**:

```bash
uv run python -c "
from pathlib import Path
from core.packs.agents import load_phase_agents
from core.packs.loader import FilesystemPackLoader
root = Path('packs')
for phase in ('research', 'propose'):
    a = load_phase_agents('terraform', phase, loader=FilesystemPackLoader(root), packs_root=root)
    src = (root / 'terraform' / 'agents' / phase / 'AGENTS.md').read_text()
    print(phase, 'unchanged:', a.body == src, '| skills:', a.skills)
"
```

**Expect**: `True` and `()` for both — FR-011, byte-identical to today.

---

## Scenario 2 — Tampered skill content stops the phase (US1 acceptance 2, FR-004)

```bash
cp packs/terraform/skills/terraform-style-guide/SKILL.md /tmp/skill.bak
printf '\n<!-- tamper -->\n' >> packs/terraform/skills/terraform-style-guide/SKILL.md
uv run pytest tests/conformance/phase_agents/ -k "digest_mismatch" -q
cp /tmp/skill.bak packs/terraform/skills/terraform-style-guide/SKILL.md
```

**Expect**: the phase fails `digest_mismatch`, `run.phase_instruction` never holds the
tampered bytes, and no model is asked to author. Restore before continuing — the row is
already green with the file intact, so a left-behind edit fails everything downstream.

---

## Scenario 3 — The record distinguishes shaped from merely present (US2, FR-005)

```bash
uv run pytest tests/component/test_run_record_names_its_packs.py tests/component/test_phase_agents_pins.py -q
```

**Expect** in `RUN_START` `content_pins`:

```
terraform/skills/terraform-style-guide@plan+write+judge
terraform/skills/terraform-style-guide-security@plan+write+judge
vault/skills/vault-secret-access@unbound
```

**Expect** in the checkpoint payload's `agent_content_pins`, after a Build that reached Write:

```
terraform/agents/write@0.2.0
terraform/agents/write@0.2.0+terraform-style-guide
terraform/agents/write@0.2.0+terraform-style-guide-security
```

**And the negative** — a Build stopped before Write carries no `…/agents/write@…+…` key at
all. This is the half that makes the record honest; a run that never reached Write must not
read as one whose Write model saw the skill.

---

## Scenario 4 — Binding is a manifest edit, not a code change (US3, SC-004)

Remove `judge` from one skill's `phases` in `packs/terraform/pack.toml`, then:

```bash
uv run python -c "
from pathlib import Path
from core.packs.agents import load_phase_agents
from core.packs.loader import FilesystemPackLoader
root = Path('packs')
a = load_phase_agents('terraform', 'judge', loader=FilesystemPackLoader(root), packs_root=root)
print([s.name for s in a.skills])
"
git checkout packs/terraform/pack.toml
```

**Expect**: one skill instead of two, with no source change. Then the refusals:

```bash
uv run pytest tests/conformance/packs/ -k "binding or unsatisfiable" -q
```

**Expect**: `phases = ["deploy"]` refuses `unknown_phase`; a phase with no `[[agents]]` pin
refuses `skill_binding_unbacked`; duplicate names refuse `duplicate_skill` — three distinct
codes, none standing in for another.

---

## Scenario 5 — The pull request says what the platform could not do (US4, FR-016)

```bash
uv run pytest tests/component/ -k "unsatisfiable_recommendations or proposal_body" -q
```

**Expect** the rendered body, between `## Provenance` and `## Limits`:

```markdown
## Adopted practice not carried out

- No registry tool runs `terraform fmt -recursive`; the authored files in this branch were not formatted by the platform.
- No registry tool runs `terraform validate`; this branch's configuration was not validated by the platform.
```

**Expect exactly two bullets**, both from `terraform-style-guide`.
`terraform-style-guide-security` declares nothing — `SECURITY.md` contains neither string, no
shell block, no tool invocation. Four bullets means the declarations were duplicated onto a
skill whose content does not make them.

**Expect** two runs over different content to produce byte-identical section text — it comes
from the manifest, not from either model (FR-018).

**Expect** the stale-declaration guard: add `terraform_fmt` as a `[[tools]]` entry with a
resolvable handler, and loading refuses `unsatisfiable_declaration_stale` rather than telling
a reviewer to do work the platform now does.

> The wording is deliberately narrow. `terraform validate` **is** run by
> `tests/evals_live/write_gates.py` against corpus tasks; what does not exist is a registry
> tool that could run it on the branch being proposed. Do not broaden these sentences to
> "the platform cannot run `terraform validate`" — that claim is false and the repository
> disproves it.

**And the bump guard** (FR-019, SC-010): change a skill's `digest` in `pack.toml` without
changing its `unsatisfiable_reviewed_at`, and loading refuses
`unsatisfiable_declaration_unreviewed`. This is what stops a skill bump from landing with a
declaration nobody re-examined — which would leave the pull request telling a reviewer that
less work remains than actually does, because the section derives from the declaration and
never from the skill's bytes.

---

## Scenario 6 — Nothing ships bound but unqualified (FR-013, SC-007)

```bash
make check
uv run pytest tests/conformance/phase_agents/test_promote_phase_agents.py -q
```

**Expect**: the scorers build the **assembled** instruction with `assemble_instruction`, so a
case whose bound skill is missing scores `fail`. They deliberately do *not* route through
`load_phase_agents` — that would deadlock, because editing a phase file makes its pin stale
and the loader would refuse `digest_mismatch` before any suite could run. Promotion still requires all five files
and passes of both `phase_agents` and `build_agents`; a single-phase loss copies zero files.

Because FR-012a edits `research` and `propose`, the five-file set re-promotes as a unit —
which is why binding and re-qualification cost nothing extra, and why no runtime state exists
for a binding that is not yet in force (FR-013a).

---

## Scenario 7 — The skill measurably changed the output (SC-002)

**Named runner: Dan McTeer.** Eval lane, not pytest — this is statistical, and the two must
never mix.

```bash
make dev-up
uv run pytest tests/evals_live/test_gates_live.py -k "authoring" -q
```

Run the Write lane 5× with the binding in place, then 5× with `phases` removed from both
skills, same n, same corpus tasks. Record in the PR: n, both rates, the delta.

**Expect**: `variable_has_validation` present in **≥ 4 of 5** runs bound, and demonstrably
less often unbound.

**Why this rule and not a more obvious one**: the phase files already hand-restate most of
the style guide — indentation, naming, `type`/`description`, `sensitive`, `for_each` over
`count`, `~>` as a pin. Measuring any of those would measure nothing, because removing the
binding leaves the rule in the instruction. `validation` blocks appear in the skill and in no
phase file. See [research R7](research.md).

**Also record E4** — the `required_version` non-regression. The skill's example uses
`>= 1.14`; the Write instruction says `>=` is not a pin; the detector agrees with the
instruction. Confirm `no_floating_version_constraint` does not fall against the pre-binding
baseline. If it does, the content-precedence sentence
([contract §7.2](contracts/pack-skill-binding.md)) is missing or too weak.

---

## Full gate before merge

```bash
make check          # lint, typecheck, unit
make conformance    # A1–A19; enclave rows if this touched durability/adapters/surfaces
make test-full      # integration, scenario, fault injection, adversarial
```

Rows A1–A21 in [contracts/conformance-phase-skill-binding.md](contracts/conformance-phase-skill-binding.md)
are hermetic and run in CI. E1–E4 have a named runner and fail loudly when the enclave is
absent — a skipped job and a passing job look the same in the checks list, and the skipped
one means nothing was tested.

**Security-maintainer review is required**: this feature edits `core/packs/manifest.py` and
the `RUN_START` `content_pins` payload, both sealed core.
