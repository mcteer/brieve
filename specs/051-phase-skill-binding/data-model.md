# Data Model: Adopted skills reach the phase that needs them

**Feature**: 051 | **Date**: 2026-08-26 | **Plan**: [plan.md](plan.md)

Entities from [spec.md](spec.md) §Key Entities, resolved against the records that already
exist. Nothing here is a new store: every field lives on a frozen dataclass that is parsed
from a manifest or assembled at bind time.

---

## 1. `SkillPin` — extended

`src/core/packs/manifest.py`. Adopted instruction content. Gains *where it applies* and
*what it recommends that this platform cannot do*.

| Field | Type | New? | Rule |
| --- | --- | --- | --- |
| `name` | `str` | — | Unique within a manifest. A duplicate refuses `duplicate_skill` |
| `path` | `str` | — | Relative to the pack directory; must resolve inside it |
| `version` | `str` | — | Upstream commit for an adopted pack |
| `digest` | `str` | — | SHA-256 of the file's bytes; verified at load **and at delivery** |
| `phases` | `tuple[str, ...]` | **new** | Phases this skill is delivered to. Default `()` — adopted and inert. Each entry must be a `PhaseName` value and must have an `[[agents]]` pin in the same manifest |
| `unsatisfiable` | `tuple[UnsatisfiableRecommendation, ...]` | **new** | Recommendations in this skill's content that no registry tool can carry out. Default `()` |
| `unsatisfiable_reviewed_at` | `str` | **new** | The skill digest against which `unsatisfiable` was last examined. **Required on every skill**, including one declaring nothing. Must equal `digest`, or loading refuses `unsatisfiable_declaration_unreviewed` (FR-019) |

**Ordering is significant.** `phases` filters; it does not order. Delivery order is the
manifest's `[[skills]]` declaration order, which `tomllib` preserves and the existing
`tuple` keeps stable (FR-006, [research R2](research.md)).

**Validation** (all in `validate_manifest`, refusing in the pack's own vocabulary):

| Condition | Reason code |
| --- | --- |
| `phases` entry is not a `PhaseName` value | `unknown_phase` |
| `phases` names a phase with no `[[agents]]` pin | `skill_binding_unbacked` |
| Two `[[skills]]` entries share a `name` | `duplicate_skill` |
| `unsatisfiable_reviewed_at` is absent or ≠ `digest` | `unsatisfiable_declaration_unreviewed` |
| A file under `packs/<name>/skills/` is not declared by any `[[skills]]` entry | not loadable by construction — see §6 |

---

## 2. `UnsatisfiableRecommendation` — new

`src/core/packs/manifest.py`. A step the adopted content recommends and this platform has no
registry tool to perform. **Declared by the pack, never inferred by a model** — a model's
account of its own work is not evidence (Principle IX), and a declaration is pinned,
reviewed, identical on every run, and checkable against the registry.

| Field | Type | Rule |
| --- | --- | --- |
| `capability` | `str` | The registry tool name that *would* satisfy it. Checked against the registry: if it exists, loading refuses `unsatisfiable_declaration_stale` (FR-017) |
| `recommendation` | `str` | Reviewer-facing sentence. Non-empty. Rendered verbatim into the pull request — never reformatted, never model-authored (FR-018) |

**Scope of "unsatisfiable"** is the **tool registry**, not the repository
([research R6](research.md)). `terraform validate` is executed by the eval lane
([write_gates.py:150](../../tests/evals_live/write_gates.py#L150)); what does not exist is a
registry tool an authoring agent can call on the branch it is proposing. Every
`recommendation` string must be true under that reading, and the contract's V4 row asserts
it.

**Terraform pack declarations** — carried by **`terraform-style-guide` only**:

| `capability` | `recommendation` |
| --- | --- |
| `terraform_fmt` | ``No registry tool runs `terraform fmt -recursive`; the authored files in this branch were not formatted by the platform.`` |
| `terraform_validate` | ``No registry tool runs `terraform validate`; this branch's configuration was not validated by the platform.`` |

**`terraform-style-guide-security` declares nothing** — `unsatisfiable = ()` with
`unsatisfiable_reviewed_at` set to its own digest. `SECURITY.md` contains neither
`terraform fmt` nor `terraform validate`, no shell block, and no tool invocation of any
kind: it is guidance on what to author, not on what to run. Declaring the two on it would
attribute a recommendation to a skill that does not make it, and would print each bullet
twice in the pull request. A declaration is *per skill* (FR-015) because it describes that
skill's content.

---

## 3. `PhaseAgents` — extended

`src/core/packs/agents.py`. Resolved, verified bytes ready to steer one phase.

| Field | Type | New? | Rule |
| --- | --- | --- | --- |
| `pack` | `str` | — | |
| `phase` | `PhaseName` | — | |
| `version` | `str` | — | The `[[agents]]` pin's version |
| `digest` | `str` | — | The `[[agents]]` pin's digest — of `AGENTS.md` alone, unchanged |
| `body` | `str` | **changed** | **The assembled instruction**: `AGENTS.md` then each bound skill. What the model receives |
| `provenance_path` | `str` | — | |
| `skills` | `tuple[DeliveredSkill, ...]` | **new** | What went into `body`, in delivery order. Empty when nothing is bound |

**`digest` stays the AGENTS.md digest.** It is a pin identity, not a hash of the assembly —
the `[[agents]]` pin shape is unchanged (spec Assumptions), and `promote_phase_agents`
rewrites it from the file's bytes. The assembly's composition is recorded by `skills`, and
each member carries its own pinned digest.

**`body` is the only field a caller may send to a model.** `bind_phase_agents` assigns it to
`run.phase_instruction`; the four entrypoint read sites are unchanged.

### `DeliveredSkill` — new

| Field | Type | Rule |
| --- | --- | --- |
| `name` | `str` | The `SkillPin` name |
| `digest` | `str` | Re-verified against the bytes read at delivery, not copied from the manifest |

---

## 4. Assembly

Deterministic, total, and the same in production and in the eval lane.

**A pure function, deliberately.** `assemble_instruction(agents_body: str, skills:
tuple[DeliveredSkill, ...], bodies: Mapping[str, str]) -> str` takes the instruction bytes as
a **parameter** rather than re-deriving them from a pin. `load_phase_agents` calls it with
the pinned, digest-verified `AGENTS.md`; the eval scorers call it with whatever bytes the
corpus case references. One assembly implementation, two callers.

If assembly instead re-derived `AGENTS.md` through `load_phase_agents`, re-qualification
would deadlock: editing a phase file makes its `[[agents]]` digest stale, `load_phase_agents`
raises `digest_mismatch` on a stale pin, the suites cannot score, and promotion — which
requires the suites to have passed — can never run. A candidate has no pin by definition;
scoring one must not require having promoted it first.

```
<AGENTS.md bytes, verbatim>

--- BEGIN PINNED SKILL: <name> (<digest>) ---
<skill bytes, verbatim>
--- END PINNED SKILL: <name> ---
```

- Skills appear in `[[skills]]` declaration order, filtered to those whose `phases` contains
  this phase.
- Delimiters are fixed literals. They are the only bytes the platform contributes, and they
  are what makes "the skill's content is present in the instruction" (US1 acceptance 1)
  assertable rather than approximate.
- Skill bytes are **never** edited, filtered, reordered internally, or truncated (ADR-0004,
  FR-015).
- A phase with no bound skills produces `body == AGENTS.md` exactly — byte-identical to
  today, including no trailing delimiter (FR-011).

**Budget**: `len(body.encode("utf-8")) > INSTRUCTION_BUDGET_BYTES` (262,144) refuses
`instruction_too_large`. Checked after assembly and before return, so no partial instruction
can leave the function ([research R4](research.md)).

**Verification at delivery** (FR-003, FR-004) — for each bound skill, in order:

| Condition | Reason code |
| --- | --- |
| File absent or unreadable | `skill_missing` |
| Bytes empty after strip | `skill_empty` |
| SHA-256 ≠ `SkillPin.digest` | `digest_mismatch` |
| Path escapes the pack directory | `skill_missing` |

Each raises `ManifestError`, which `_bind_phase_or_fail` already converts to a phase failure
with the reason recorded. There is no fallback: neither delivering unverified content nor
proceeding without it (FR-004).

---

## 5. Content pin record — extended

Two records, because one cannot answer both halves of FR-005
([research R11](research.md)).

### 5a. `content_pins` at `RUN_START` — what is *bound*

`surfaces/toolset.py::content_pins`. Static, manifest-derived, written once before any phase
runs. Key grammar changes for skills only:

| Today | New | Meaning |
| --- | --- | --- |
| `terraform/terraform-style-guide` | `terraform/skills/terraform-style-guide@plan+write+judge` | Bound to those phases |
| `vault/vault-secret-access` | `vault/skills/vault-secret-access@unbound` | Adopted, pinned, delivered nowhere |

- Phase names in the suffix are joined by `+` in `PHASE_ORDER` order — not manifest order —
  so the key is stable when a manifest's `phases` array is rewritten in a different order.
- `skills/` is inserted so the namespace matches the existing `agents/` one and a key cannot
  collide with a pack name.
- Pack and `[[agents]]` keys are unchanged.

This record **cannot** say what was delivered: it is written at `RUN_START`, before any phase
executes, so US2 acceptance 2 (a run that stopped before Write) is unanswerable here.

### 5b. Per-phase delivery — what actually *reached a model*

`run.agent_content_pins`, accumulated by `bind_phase_agents` as each phase binds.

| Key | Value |
| --- | --- |
| `terraform/agents/write@0.2.0` | the AGENTS.md digest (**today's shape, unchanged**) |
| `terraform/agents/write@0.2.0+terraform-style-guide` | that skill's digest, as verified at delivery |

**This map is currently never written anywhere.** `bind_phase_agents` sets it on the run
object ([phase_agents.py:41-43](../../src/surfaces/dispatch/phase_agents.py#L41-L43)) and no
checkpoint, audit event, or result body carries it — a 049 gap this feature must close for
US2 to mean anything. It joins the checkpoint payload under `agent_content_pins`, written by
`_payload_with_progress` alongside `PROGRESS_KEY`, so it accumulates with the run and a run
that stopped before Write carries no Write key.

**Identity only.** Names and digests, never bodies — the property
[test_pins_are_identity_only.py](../../tests/conformance/phase_agents/test_pins_are_identity_only.py)
asserts today, extended to the skill keys.

---

## 6. Skill files not in the manifest (FR-008)

No new mechanism. `load_phase_agents` reads a skill only by iterating
`manifest.skills`, and every path is resolved under the pack directory and digest-checked. A
file on disk that no `[[skills]]` entry names is never opened, so it cannot be delivered —
structurally, not by a rule somebody follows. `packs/terraform/skills/LICENSE` and
`PROVENANCE.md` are the live instances, and a conformance row asserts neither reaches an
instruction.

---

## 7. `Proposal` — extended

`src/core/authoring/proposal.py`.

| Field | Type | Rule |
| --- | --- | --- |
| `unsatisfiable_recommendations` | `tuple[str, ...]` | The `recommendation` strings of every skill bound to any phase of the bound pack, in `[[skills]]` order then declaration order within a skill. Default `()` |

**One name for one thing.** The spec's entity is *unsatisfiable recommendation*; the field,
the manifest table, and every reference use that word. `## Adopted practice not carried out`
is the section heading a reviewer reads and is prose, not a second vocabulary.

Rendered as a `## Adopted practice not carried out` section, between `## Provenance` and
`## Limits`, matching the ordering rationale already recorded in `render` — what was
proposed, where it came from, **what adopted practice was not carried out**, then what is not
covered.

**Kept out of `limits`.** `limits` is `DERIVATIVE_LIMIT + disclosures`, and `disclosures` are
run-derived (truncated reads). This text must be run-independent to satisfy FR-018, so it
cannot share a field with run-derived content.

**Why "every skill bound to any phase" is run-independent**: a run that opens a pull request
has necessarily executed all five phases — `open_proposal` follows the Propose bind, which
follows Judge permitting publication, which follows Write, Plan and Research. So "bound to a
phase that ran" and "bound to any phase" name the same set at the only moment the question is
asked, and the implementation reads the manifest rather than the progress record
([research R10](research.md)).

Empty tuple renders no section. A pack with no bound skills, or bound skills declaring
nothing unsatisfiable, produces today's body exactly.

---

## Reason codes added

All raise `ManifestError` and travel the existing `_bind_phase_or_fail` path. SC-005 requires
each to be distinct and none reported as another.

| Code | Raised when | Stage |
| --- | --- | --- |
| `skill_missing` | Bound skill's file absent, unreadable, or outside the pack | Delivery |
| `skill_empty` | Bound skill's bytes are empty | Delivery |
| `digest_mismatch` | Bound skill's bytes ≠ pin *(existing code, new site)* | Delivery |
| `instruction_too_large` | Assembled instruction over `INSTRUCTION_BUDGET_BYTES` | Delivery |
| `unknown_phase` | `phases` entry is not a `PhaseName` *(existing code, new site)* | Load |
| `skill_binding_unbacked` | `phases` names a phase with no `[[agents]]` pin | Load |
| `duplicate_skill` | Two `[[skills]]` share a `name` | Load |
| `unsatisfiable_declaration_unreviewed` | `unsatisfiable_reviewed_at` is absent or ≠ the skill's `digest` | Load |
| `unsatisfiable_declaration_stale` | A declared `capability` is offered by the registry | Registration |
