# Conformance: Adopted skills reach the phase that needs them (051)

Every row is blocking from the moment its feature lands (ADR-0047). A row that no automated
check executes names the party who runs it before merge (constitution v1.6.0, Quality Gates).

## Hermetic / CI

| ID | Claim | How it can lose |
| --- | --- | --- |
| A1 | A phase bound to a skill receives that skill's full bytes in `PhaseAgents.body`, between the fixed delimiters | Body equals `AGENTS.md`; skill content partially present; delimiters absent or reworded |
| A2 | Delivery order is `[[skills]]` declaration order; two loads of identical manifest content produce byte-identical `body` | Sorted-by-name order, set iteration order, or two loads differing |
| A3 | A phase bound to no skills produces `body` byte-identical to its `AGENTS.md`, including trailing bytes | A delimiter, blank line, or header appears when nothing is bound |
| A4 | A bound skill whose bytes no longer hash to its pin fails the phase `digest_mismatch`; `run.phase_instruction` never holds the mismatched content | Bind succeeds; body carries unverified bytes; a different reason code |
| A5 | Missing, unreadable, empty, and pack-escaping bound skills fail `skill_missing` / `skill_empty` respectively, each distinct | Any collapses into another code, or a phase proceeds without the skill |
| A6 | An assembly over `INSTRUCTION_BUDGET_BYTES` fails `instruction_too_large`; nothing truncated is ever returned | A truncated body is delivered, or the check runs after return |
| A7 | `phases` naming a non-`PhaseName` refuses `unknown_phase`; naming a phase with no `[[agents]]` pin refuses `skill_binding_unbacked`; duplicate `[[skills]]` names refuse `duplicate_skill` | Load succeeds; a shared code for all three |
| A8 | `packs/terraform/skills/LICENSE` and `PROVENANCE.md` — present on disk, absent from `[[skills]]` — never appear in any phase's `body` | Undeclared file content reaches an instruction |
| A9 | **No shipped `AGENTS.md` in any pack names a skill it is not bound to** (FR-010, SC-006). Terraform `research` and `propose` no longer name either skill; `plan`, `write`, `judge` do and are bound | A phase file names a skill absent from its `phases`, in either pack |
| A10 | Every phase bound to a skill states both precedences — registry bounds capability; the phase file governs a content conflict (contract §7.2) | Either sentence missing from a bound phase file |
| A11 | **No file under `src/` names a skill, a binding, or a recommendation string.** Adding a binding is a `pack.toml` edit alone (SC-004) | A skill name, phase-binding table, or recommendation literal appears in platform source |
| A12 | `RUN_START` `content_pins` key for a bound skill is `<pack>/skills/<name>@<phases in PHASE_ORDER joined by +>`; for an unbound one, `@unbound`. Vault's skill records `@unbound` | Old `<pack>/<name>` shape; manifest order in the suffix; a bound and an unbound skill indistinguishable |
| A13 | `run.agent_content_pins` is **written into the checkpoint payload**, and a run stopped before Write carries no `…/agents/write@…+terraform-style-guide` key (US2 acceptance 2) | Pins held in memory only; a not-yet-run phase's skill recorded as delivered |
| A14 | Per-phase pins are identity only — names and digests, never instruction or skill bodies | A body fragment appears in the recorded map |
| A15 | A manifest declaring `unsatisfiable.capability` that the registry offers refuses `unsatisfiable_declaration_stale`, and the refusal is order-independent across the load set | Load succeeds; refusal depends on which pack registered first |
| A16 | A pull request from a Terraform Build carries `## Adopted practice not carried out` between Provenance and Limits, naming **exactly two** recommendations verbatim — both from `terraform-style-guide`; two runs of different content produce identical section bytes | Section absent, reworded, model-authored, differing between runs, or carrying four bullets because `terraform-style-guide-security` declared recommendations its content does not make |
| A17 | A pack with no bound skills, or none declaring unsatisfiable recommendations, renders today's PR body exactly — no empty section | An empty heading ships |
| A18 | `score_phase_agents_case` / `score_build_agents_case` score the **assembled** instruction via `assemble_instruction`; a case whose bound skill is missing scores `fail` | Scorers read `AGENTS.md` alone; a phase qualifies on bytes production does not send |
| A19 | `terraform fmt` and `terraform validate` are **not** registry tool names (the premise of the declarations), asserted against `known_tools` | Either becomes a registry tool with the declaration still in the manifest — caught here as well as by A15 |
| A20 | A `[[skills]]` entry whose `digest` changes without `unsatisfiable_reviewed_at` changing to match refuses `unsatisfiable_declaration_unreviewed` at load; the rule applies to a skill declaring nothing as well as one declaring something (FR-019) | A bump loads with a declaration nobody re-examined, so the pull request understates what a person still has to do |
| A21 | `assemble_instruction` is a pure function taking instruction bytes as a parameter; scoring a candidate that has no `[[agents]]` pin succeeds | The scorer re-derives bytes through `load_phase_agents`, so an edited phase file deadlocks re-qualification on its own stale pin |

**Runner**: CI (`make check`, `make conformance`). Rows A1–A21 are hermetic — no enclave, no
model, no network.

## Enclave / named runner

| ID | Claim | Runner |
| --- | --- | --- |
| E1 | Connected, restricted and air-gapped profiles deliver the identical assembled instruction — nothing is fetched at phase start | Dan — allocation without outbound web still binds Write with both skills |
| E2 | **SC-002**: a style rule the vendored skill states, no phase file restates, and the unaided model does not reliably follow — `variable` blocks carrying `validation { condition, error_message }` — is present in authored output in **≥ 4 of 5** runs with the binding, and demonstrably less often with it removed. Same n, both rates and the delta recorded | Dan — eval lane |
| E3 | **SC-007**: `phase_agents` and `build_agents` both pass over assembled content before the five-file set promotes; a losing set copies zero files | Dan — eval lane |
| E4 | No `required_version` regression: with both skills delivered, `no_floating_version_constraint` does not fall against the pre-binding baseline on the same corpus tasks (contract §7.2 rule 2 is what prevents it) | Dan — eval lane |

**Named runner**: Dan McTeer (maintainer). Rows fail loudly when the enclave or eval broker
is absent — do not skip green.

### Why E2 names that rule and not another

Research R7 found that `packs/terraform/agents/write/AGENTS.md` §"Required HashiCorp
practice" already restates most of `SKILL.md` by hand: indentation, naming, `type` and
`description` on variables, `sensitive`, output descriptions, `for_each` over `count`,
meta-argument ordering, standard file names, `~>` as a pin. Measuring SC-002 on any of those
would measure nothing — removing the binding leaves the rule in place, and the spec's own
Independent Test says a rule that passes with the skill absent is not evidence.

`validation` blocks appear in `SKILL.md` twice
([48-57](../../../packs/terraform/skills/terraform-style-guide/SKILL.md#L48-L57),
[153-163](../../../packs/terraform/skills/terraform-style-guide/SKILL.md#L153-L163)), in no phase
file, and are not something a base model emits unprompted. E2 requires a new
`variable_has_validation` property in `tests/evals_live/authoring_properties.py` and a corpus
task in `evals/authoring/corpus.toml` that asks for a constrained input.

**The detector must be able to fail.** Following the precedent that
`static_credential_lookalike` sets for the existing properties, the corpus supplies a case
with a `variable` block carrying `type` and `description` but no `validation`, and a row
requires the detector to score it `fail`.

### E4 exists because two pinned documents disagree

`SKILL.md` §Version Pinning shows `required_version = ">= 1.14"`. `write/AGENTS.md` §Pins
says `>=` is not a pin and instructs fixing every floating constraint. The eval detector
agrees with the instruction. Today the two never meet; this feature puts them in one context.
E4 is the row that catches the regression if §7.2 rule 2 is dropped or weakened.

## Implementation PR named-runner record

To be filled on `feat/051-phase-skill-binding`. Live rows are not pytest-on-model-wording.

| Row | Named runner | Status |
| --- | --- | --- |
| E1 | Dan McTeer | Due on the implementation PR |
| E2 | Dan McTeer | Due on the implementation PR — record n, both rates, the delta |
| E3 | Dan McTeer | Due on the implementation PR |
| E4 | Dan McTeer | Due on the implementation PR — record the baseline it is compared against |

## Security-maintainer review

Required. This feature edits `core/packs/manifest.py` (registry schema) and the `RUN_START`
`content_pins` payload (audit schema), both named sealed core. The spec is approved; the
implementation PR must request the review (constitution Principle V, `AGENTS.md` rule 4).
