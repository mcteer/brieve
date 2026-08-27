# Contract: Phase–skill binding (051)

**Stability**: interface stable now. This contract touches sealed core — `core/packs/manifest.py`
is a registry schema and `content_pins` is `RUN_START` audit payload — so every encoding below
is pinned here rather than decided at implementation time, and the implementation PR requests
security-maintainer review (constitution Principle V).

---

## 1. Manifest surface

### 1.1 `[[skills]].phases`

```toml
[[skills]]
name    = "terraform-style-guide"
path    = "skills/terraform-style-guide/SKILL.md"
version = "8c6573abbd21e8094fab8f538eb5f97db63133fd"
digest  = "fea8a0eadf68f1ac45cae3b1d6dc4c66b489fb6e40a3d41762120059c49540c2"
phases  = ["plan", "write", "judge"]
```

- **Type**: array of strings. **Optional**; absent ≡ `[]` ≡ adopted and inert.
- **Domain**: exactly the values of `core.authoring.progress.PhaseName` — `research`, `plan`,
  `write`, `judge`, `propose`. The closed set from `PHASE_ORDER`; this feature adds no phase.
- **Order is not significant.** `phases` filters. Delivery order comes from `[[skills]]`
  declaration order (§2.2).
- **Duplicates within one `phases` array** are collapsed; a skill is delivered to a phase once.

### 1.2 `[[skills.unsatisfiable]]`

```toml
[[skills.unsatisfiable]]
capability     = "terraform_fmt"
recommendation = "No registry tool runs `terraform fmt -recursive`; the authored files in this branch were not formatted by the platform."
```

- **`capability`**: the registry tool name that would satisfy the recommendation. Required,
  non-empty.
- **`recommendation`**: the reviewer-facing sentence, rendered verbatim. Required, non-empty.
  Must be true of the **tool registry**, not of the repository — the eval lane runs
  `terraform validate` and a claim that the platform cannot is false (research R6).

### 1.2a `[[skills]].unsatisfiable_reviewed_at`

The skill digest against which that skill's `unsatisfiable` block was last examined.
**Required on every `[[skills]]` entry**, including one declaring nothing — "nothing here is
unsatisfiable" is itself a claim that goes stale on a bump. Must equal the entry's `digest`;
otherwise loading refuses `unsatisfiable_declaration_unreviewed` (FR-019).

A bump therefore cannot land silently: changing `digest` without touching this field refuses
at load, and touching it requires reading the block directly above it. The pull request
derives from the declaration and never from the skill's bytes (FR-018), so a declaration that
lags the content would tell a reviewer that less work remains than actually does.

### 1.3 What no platform source may contain

No file under `src/` may name a skill, a skill-to-phase binding, or an unsatisfiable
recommendation string (FR-002, SC-004). Adding or removing a binding is a `pack.toml` edit
and nothing else. Asserted by row A11.

---

## 2. Assembly

### 2.1 Format

```
<AGENTS.md bytes, verbatim>

--- BEGIN PINNED SKILL: <name> (<digest>) ---
<skill bytes, verbatim>
--- END PINNED SKILL: <name> ---
```

Delimiters are fixed literals; `<digest>` is the full 64-character hex SHA-256. One blank
line separates `AGENTS.md` from the first delimiter and each `END` from the next `BEGIN`.
These delimiter bytes are the **only** content the platform contributes.

### 2.2 Order

`AGENTS.md`, then each bound skill in `[[skills]]` **declaration order**. Identical manifest
content produces an identical instruction, byte for byte (FR-006).

### 2.3 Empty binding

A phase with no bound skills produces `body == AGENTS.md` exactly — no delimiter, no trailing
newline change. Byte-identical to today (FR-011).

### 2.4 Budget

`INSTRUCTION_BUDGET_BYTES = 256 * 1024` (262,144). Measured as
`len(body.encode("utf-8"))` after assembly, before return. Over it: `instruction_too_large`.
**Never truncate** (FR-009). The value is fixed with its reasoning in research R4; raising it
to make content fit is the failure `READ_BUDGET_BYTES` documents.

### 2.5 One implementation, two callers

Assembly exists once, as a **pure function** in `core/packs/agents.py`:

```python
def assemble_instruction(
    agents_body: str,
    skills: tuple[DeliveredSkill, ...],
    bodies: Mapping[str, str],
) -> str: ...
```

It takes the instruction bytes as a parameter and never re-derives them from a pin.

- `load_phase_agents` calls it with the pinned, digest-verified `AGENTS.md`.
- `score_phase_agents_case` / `score_build_agents_case` call it with the bytes the corpus case
  references, plus the pack's bound skills resolved and digest-verified from the manifest.

**Why not have the scorer call `load_phase_agents`**: re-qualification would deadlock. Editing
a phase file makes its `[[agents]]` digest stale; `load_phase_agents` raises `digest_mismatch`
on a stale pin; the suites cannot score; and `promote_phase_agents` requires the suites to
have passed. A candidate has no pin by definition, and scoring one must not require having
promoted it first.

A second assembly *implementation* would still let a suite pass on bytes production never
sends — hence one function, called twice.

---

## 3. Refusals

Every code is distinct and none is reported as another (SC-005).

| Code | Stage | Condition |
| --- | --- | --- |
| `unknown_phase` | Load | A `phases` entry is not a `PhaseName` value |
| `skill_binding_unbacked` | Load | A `phases` entry names a phase with no `[[agents]]` pin in the same manifest |
| `duplicate_skill` | Load | Two `[[skills]]` entries share a `name` |
| `unsatisfiable_declaration_unreviewed` | Load | `unsatisfiable_reviewed_at` is absent or does not equal the entry's `digest` |
| `unsatisfiable_declaration_stale` | Registration | A declared `capability` is offered by the registry (§4) |
| `skill_missing` | Delivery | Bound skill's file is absent, unreadable, or resolves outside the pack directory |
| `skill_empty` | Delivery | Bound skill's bytes are empty after strip |
| `digest_mismatch` | Delivery | Bound skill's bytes do not hash to its pin |
| `instruction_too_large` | Delivery | Assembled instruction exceeds the budget |

Delivery-stage refusals raise `ManifestError` and travel the existing
`_bind_phase_or_fail` path, failing the phase with the reason recorded. **No fallback
exists**: neither delivering unverified content nor proceeding without a bound skill
(FR-004).

---

## 4. FR-017 — the stale-declaration check

**Where**: `core/packs/registration.py::load_packs`, after every pack in the set has
registered. **Not** in `PackLoader.load` (registry-blind) and **not** in `register_pack`
(order-dependent — pack B's declaration would refuse only if pack A registered first, and
load order changes without anybody deciding it did).

**What counts as offered**: `capability` appears in `registry.tool_names()` after the set
registers, **or** in `bindings.handlers`. The handler table is included because a capability
with a platform handler is one somebody has built; the declaration is stale from that moment.

**What does not count**: anything reachable only outside the registry — a subprocess in
`tests/`, a Makefile target, a CI step. `tests/evals_live/write_gates.py` invoking
`terraform validate` contributes to neither set (research R6).

**Effect**: refuses the whole load set, consistent with `load_packs`'s existing
all-or-nothing contract.

**Two load paths, deliberately.** `load_phase_agents` calls `loader.load(name)` directly
([agents.py:40](../../src/core/packs/agents.py#L40)) and does **not** run this check — it has
no registry, and giving it one would put a registry dependency on the content path. Every run
reaches `load_packs` through `build_registry` at startup, so a manifest with a stale
declaration never gets as far as a phase bind. The direct path stays registry-blind on
purpose; the check lives where the registry does.

---

## 5. `content_pins` key grammar (`RUN_START`) — pinned

Audit payload. The grammar is fixed here, not at implementation time.

```
<pack>@<pack-version>                              # unchanged
<pack>/agents/<phase>@<agents-version>             # unchanged
<pack>/skills/<skill-name>@<binding>               # CHANGED from <pack>/<skill-name>
```

`<binding>` is either:

- phase names joined by `+` in **`PHASE_ORDER`** order — `plan+write+judge` — so the key is
  stable when a manifest's `phases` array is rewritten in a different order; or
- the literal `unbound` when `phases` is empty.

**Migration**: the skill key changes shape, and **no compatibility shim ships**.

Be precise about why that is safe, because the obvious rationale is wrong. `run.py`'s own
docstring says the payload is "what lets a resumed run's content be compared to what the
original run actually loaded" — that describes a capability, **not an implemented
comparison**. `resume_run` never reads `content_pins`: zero occurrences in
`src/core/durability/resume.py`. So changing the key shape has no effect at resume, because
nothing at resume looks.

The consumers are two tests — `tests/component/test_run_record_names_its_packs.py` and
`tests/component/test_phase_agents_pins.py` — updated by T014. The record is evidence read by
a person or an auditor after the fact, and for that reader old and new keys are visibly
different, which is the property that matters.

**Do not write, here or in a task, that a pre-change run resumed post-change "must not
silently match".** It does proceed, because no comparison exists. Building that comparison is
a separate feature; misstating it as already present is the overstated-evidence failure this
whole feature exists to remove.

---

## 6. Per-phase delivery record

`run.agent_content_pins`, accumulated at each bind:

```
<pack>/agents/<phase>@<agents-version>                    → AGENTS.md digest   # unchanged
<pack>/agents/<phase>@<agents-version>+<skill-name>       → skill digest       # new
```

Skill digests are the values **re-verified at delivery**, not copied from the manifest.

**Written, not just held.** These pins join the checkpoint payload under the
`agent_content_pins` key via `_payload_with_progress`. Today the map is set on the run object
and never written anywhere — a 049 gap this feature closes, because US2 acceptance 2 (a run
that stopped before Write records no Write skill) is otherwise unobservable.

**Identity only** — names and digests, never bodies.

---

## 7. Phase instruction obligations

### 7.1 Prose may not outrun binding (FR-010)

No shipped `AGENTS.md` may name a skill the phase is not bound to. Enforced by row A9, not by
review.

Terraform today: all five files read *"Practice is this file and the pinned skills
`terraform-style-guide` / `terraform-style-guide-security`"*. After this feature, `plan`,
`write` and `judge` keep it; `research` and `propose` drop it (FR-012a).

### 7.2 Precedence, stated in the phase file

Every phase bound to at least one skill states both precedences:

1. **Capability** — the registry bounds what can be done; adopted practice does not widen it.
   A step naming a capability the registry does not offer is not performed and not reported as
   performed (FR-014).
2. **Content** — where this file and a delivered skill differ on a concrete rule, this file
   governs, and the difference is not a licence to do neither.

Rule 2 is required by FR-001 + FR-012 the moment both documents share a context: the skill's
`required_version = ">= 1.14"` example contradicts the Write instruction's "`>=` is not a
pin", and the eval detector `no_floating_version_constraint` agrees with the instruction
(research R8). Editing the skill is forbidden (ADR-0004), so naming which document wins is
the only available move. **This widens FR-014 and needs a spec sentence — analyze must carry
it to clarify.**

---

## 8. Pull request surface

`Proposal.unsatisfiable_recommendations: tuple[str, ...]` → section `## Adopted practice not
carried out`, between `## Provenance` and `## Limits`.

**Contents**: the `recommendation` string of every `[[skills.unsatisfiable]]` entry of every
skill bound to any phase of the bound pack, in `[[skills]]` declaration order and declaration
order within a skill. Rendered verbatim, one `- ` bullet each.

**For the Terraform pack this is exactly two bullets**, both from `terraform-style-guide`.
`terraform-style-guide-security` declares nothing: `SECURITY.md` contains no shell block and
no tool invocation. Declaring the same two on both skills would print each bullet twice and
would attribute a recommendation to a skill that does not make it.

**Derivation**: the manifest, and nothing else. Never the progress record, never a model's
report (FR-018). Run-independent because a run that opens a pull request has necessarily
executed all five phases (research R10).

**Empty**: no section. A pack with no bound skills, or none declaring anything unsatisfiable,
renders today's body exactly.

---

## 9. Re-qualification (FR-013, SC-007)

`score_phase_agents_case` and `score_build_agents_case` score the **assembled** instruction —
`AGENTS.md` plus that phase's bound skills — resolved through `load_phase_agents`. Scoring
the `AGENTS.md` file alone would green the gate without looking at the bytes the model
receives (ADR-0047).

Corpus `instruction_ref` / `set_ref` keep naming `AGENTS.md` paths; the scorer derives the
pack from the path.

**Promotion is unchanged and all-five-or-none.** `promote_phase_agents` already requires all
five files and passes of both `phase_agents` and `build_agents`. Because FR-012a edits
`research` and `propose`, a full re-promotion is forced regardless of how many phases bind —
which is why binding and re-qualification shipping together costs nothing extra (FR-013a: no
runtime state exists for a binding that is not in force).

**Injection lens**: `promote_phase_agents` lenses each `AGENTS.md`; `promote_skill` lenses
each skill. Combined content is lensed **in halves**, and no third pass is added — this
feature contributes no new content, only a new adjacency. Recorded because "we lensed the
parts" and "we lensed the whole" are different claims.
