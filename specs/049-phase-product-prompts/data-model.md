# Data Model: Product-and-phase Build instructions

**Feature**: `specs/049-phase-product-prompts` | **Date**: 2026-08-19

Entities the platform persists or validates. Runtime orchestration belongs in dispatch;
this file names records and transitions.

---

## AgentPin

Pinned executed instruction for one Build phase of one pack. Manifest data, never code.

| Field | Type | Rules |
| --- | --- | --- |
| `phase` | `str` | Must be a `PhaseName` value: `research` \| `plan` \| `write` \| `judge` \| `propose`. Unknown → `unknown_phase`. Duplicate in one pack → `duplicate_phase` |
| `path` | `str` | Relative to the pack directory. Canonical: `agents/<phase>/AGENTS.md`. Must not resolve outside the pack directory |
| `version` | `str` | Non-empty. Identity the run record stores alongside the digest |
| `digest` | `str` | SHA-256 hex of the `AGENTS.md` bytes. Load verifies. Mismatch → `digest_mismatch` |

Relationships: many `AgentPin` per `PackManifest` (`PackManifest.agents`). An authoring
pack has exactly five, one per `PhaseName`.

Not the instruction body. Not a skill (`SkillPin` remains skills).

---

## PhaseAgents

Resolved, verified bytes ready to steer one phase. Produced by `load_phase_agents`.

| Field | Type | Rules |
| --- | --- | --- |
| `pack` | `str` | Bound pack name (from `AuthoringRequest.pack` / single `RUN_PACKS` entry) |
| `phase` | `PhaseName` | Current phase |
| `version` | `str` | From `AgentPin` |
| `digest` | `str` | From `AgentPin`, verified |
| `body` | `str` | UTF-8 `AGENTS.md` contents. Empty after strip → `agents_empty`; phase does not start |
| `provenance_path` | `str` | Sibling `agents/<phase>/PROVENANCE.md` (required present and non-empty; not executed) |

Validation: if `load_phase_agents` cannot produce this record, the phase is marked failed
(`PhaseStatus.FAILED`) with a user-safe reason; later phases stay pending; no PR.

---

## Instruction set

The five `PhaseAgents` for one pack that production may execute.

| Field | Type | Rules |
| --- | --- | --- |
| `pack` | `str` | One pack |
| `pins` | `tuple[AgentPin, ...]` | Length 5, all phases present |
| `suites_passed` | `tuple[str, ...]` | Must include `phase_agents` and `build_agents` before `promote_phase_agents` returns |

State: **candidate** (under `evals/prompt-tune/candidates/`) → **promoted** (bytes +
digests in `packs/<pack>/` after `promote_phase_agents`). No boolean flag. Unpromoted
candidates are not on the allocation's load path.

---

## Provenance record

Reviewable sibling, not executed.

| Field | Content |
| --- | --- |
| Sources consulted | Named public documents / style guides (URLs or titles + retrieval date) |
| Authorship date | ISO date |
| Injection-lens note | Human review, same discipline as skill PROVENANCE.md |

Missing or empty file → `agents_provenance_missing` at load. Body is not concatenated into
the model prompt.

---

## ChoiceRequest (extension)

Existing core record. Additive field:

| Field | Type | Rules |
| --- | --- | --- |
| `instruction` | `str` | Default `""`. Build phase: the `PhaseAgents.body`. Ask: remains empty. Chooser must not substitute a generic steer when empty on a path that required a bind — dispatch fails before choose |

Existing fields (`task`, `permitted`, `step_index`, `attempt`, `refused`) unchanged.

---

## Run content pins (extension)

`content_pins` / `RUN_START` payload gains keys:

```text
{pack}/agents/{phase} = <digest>
```

for each phase this run actually started. Join on `correlation_id`. Do not persist the
instruction body in audit.

---

## Eval cases

### `phase_agents` (individual)

| Field | Rules |
| --- | --- |
| `id` | Unique per pack file |
| `suite` | `phase_agents` |
| `phase` | One `PhaseName` |
| `instruction_ref` | Path or digest under test |
| `expected` | Mechanical: `pass` or `fail` |
| Floor | ≥5 cases per phase; **at least one `fail`** case per phase (ADR-0047) |

Scored without a live model in the merge-blocking lane (recorded / property checks). Live
GEPA uses the same case identities.

### `build_agents` (joint)

| Field | Rules |
| --- | --- |
| `id` | Unique |
| `suite` | `build_agents` |
| `set_ref` | The five-file set |
| `expected` | `pass` or `fail` |
| Floor | ≥5 cases; **at least one `fail`** for a set that is individually plausible and jointly poisonous |

---

## State transitions

```text
phase start
  → bind exactly one pack (else pack_unbound / pack_ambiguous)
  → load_phase_agents
       fail → PhaseStatus.FAILED, no later phase, no PR
       ok   → record pin on run, ChoiceRequest.instruction = body, phase work proceeds
phase complete / fail (047 progress machine unchanged)
```

Promotion:

```text
GEPA per file (must be able to lose)
  → DSPy five-predictor compile (must be able to lose)
  → promote_phase_agents (provenance + lens + both suites)
       refuse → candidates stay out of packs/
       ok     → copy into packs/<pack>/agents/, update [[agents]] digests
```

Ask: no transition; `instruction` stays empty.
