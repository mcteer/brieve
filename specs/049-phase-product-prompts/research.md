# Research: Product-and-phase Build instructions

**Feature**: `specs/049-phase-product-prompts` | **Date**: 2026-08-19

Decisions, not forks. Checked against merged authoring (038/041/042/047), pack loading (013),
choice (040), promotion (013/038), and constitution v1.6.0.

---

## R1 — Exact filesystem layout

**Decision**: Each phase instruction is exactly:

```text
packs/<pack>/agents/<phase>/AGENTS.md
packs/<pack>/agents/<phase>/PROVENANCE.md
```

`<phase>` is `PhaseName.value`: `research`, `plan`, `write`, `judge`, `propose`. Ten
`AGENTS.md` files ship in this feature (terraform × 5, vault × 5). The repository-root
contributor `AGENTS.md` is never on this path.

**Rationale**: Spec clarification 2026-08-19 requires one `AGENTS.md` per phase per product,
not a combined prompt, not `pack.toml` prose, not a skill. Directory-per-phase makes the
phase identity visible without opening the file, and keeps provenance beside the executed
bytes the way adopted skills already do (`packs/terraform/skills/PROVENANCE.md`).

**Alternatives considered**: `packs/<pack>/AGENTS.<phase>.md` (flatter; weaker sibling
provenance). `packs/<pack>/skills/<phase>/AGENTS.md` (rejected: FR-016 — a skill path would
invite SKILL.md substitution). A single `AGENTS.md` with headings (rejected: spec).

---

## R2 — Manifest pin shape

**Decision**: `pack.toml` gains `[[agents]]` tables, parallel to `[[skills]]`:

```toml
[[agents]]
phase = "research"
path = "agents/research/AGENTS.md"
version = "0.1.0"
digest = "<sha256 of AGENTS.md bytes>"
```

Dataclass: `AgentPin(phase: str, path: str, version: str, digest: str)` on
`PackManifest.agents`. Loader verifies the digest (reason `digest_mismatch`), refuses a
missing or empty `AGENTS.md` (`agents_missing` / `agents_empty`), refuses a missing or empty
sibling `PROVENANCE.md` (`agents_provenance_missing`), refuses an unknown or duplicate
`phase` (`unknown_phase` / `duplicate_phase`).

A pack that **declares an authoring workflow** (existing `packs_declaring_authoring` rule:
workflow name contains `"author"`) MUST declare all five phases (`agents_incomplete`). Packs
that do not author need no `[[agents]]`. A Build that somehow reaches a pack without them
fails at phase start, not by falling back.

The `[[agents]]` table is a pin, not the instruction (FR-016).

**Rationale**: 013 already made "pinned" checkable with `SkillPin.digest` at load, not at
review. Phase instructions are executed artifacts (ADR-0030) and inherit that mechanism.
Authoring-only completeness avoids forcing Ask-only packs to ship Build files.

**Alternatives considered**: Pin only in git with no digest (invisible drift). Reuse
`[[skills]]` names (FR-016). Require `[[agents]]` of every pack (Ask-only packs would ship
dead files or the loader would lie).

---

## R3 — Product binding (no picker, no default)

**Decision**: A Build is bound to exactly one pack name already carried as
`AuthoringRequest.pack` and dispatched as `RUN_PACKS` / job meta `packs`.

- **Zero packs** or **empty pack** → refuse `pack_unbound`. Do not default to terraform.
- **Two or more packs** → refuse `pack_ambiguous`. Do not concatenate instructions.
- **One pack** → that pack's `[[agents]]` for the current `PhaseName`.

Propose chat (047) remains Terraform-shaped: `src/surfaces/api/propose.py` continues to set
`pack="terraform"` as an **explicit surface binding**, not as a fallback when the pack is
unknown. Vault-bound five-phase steering is exercised by hermetic tests and the eval lane
constructing `AuthoringRequest(pack="<vault pack name>")`, and by any authoring-tier run
whose `RUN_PACKS` is exactly that pack (042's request already composes `AuthoringRequest`).
This feature does not add a portal product picker (spec assumption).

`load_phase_agents` takes a pack name string and a `PhaseName`. It never mentions terraform
or vault. Isolation is "the bound pack's bytes versus any other loaded pack's bytes."

**Rationale**: Spec edge case and FR-002/FR-005. Today's hardcoded `"terraform"` in Propose
is a decided 047 product, not an implicit default for an ambiguous run.

**Alternatives considered**: Infer product from task text (ambiguous, not fail-closed).
Concatenate all packs (spec forbids). Portal picker (FR-013 / out of scope).

---

## R4 — How the file reaches the model

**Decision**: At the start of each 047 phase, dispatch calls
`load_phase_agents(pack, phase)` and, on success, records identity+version+digest, then
passes the file body as `ChoiceRequest.instruction`.

`ChoiceRequest` gains `instruction: str = ""`. Empty means Ask / non-Build: the chooser
must not invent a substitute. `resolve_step_tool` forwards the field.
`adapters.model_chooser` prepends non-empty `request.instruction` to the **system** prompt
for that call. Existing `_AUTHORING_*_HINT` strings stay as **tool-schema** hints
(product-blind: `read_subject` / `author_file` argument shapes). They are not a fallback
when `instruction` is empty on a Build phase — dispatch fails before choose.

Judge uses the judge cell (ADR-0039) plus the Judge `AGENTS.md`. Write uses the write cell
plus the Write `AGENTS.md`. A product-specific Judge file does not move judging onto the
write binding (FR-015). ADR-0067 stays Proposed and is not used as a requirement.

Ask never sets `instruction` (FR-014).

**Rationale**: Core stays the source of the bytes; the adapter only concatenates. Putting
product practice into `model_chooser` would teach the adapter Terraform. Stuffing the file
into `task` would mix the person's request with platform instructions in the evidence.

**Alternatives considered**: Adapter-hardcoded product hints (Principle I). Task-field
concatenation (pollutes the person's words). Fetching skills instead (FR-016).

---

## R5 — GEPA then DSPy, extra `prompt-tune`, never runtime

**Decision**: Two named passes, both offline:

1. **Individual (GEPA).** For each phase file, a one-predictor `dspy.Module` whose
   instruction is that `AGENTS.md` is compiled with **`dspy.GEPA`** against the phase
   measure (`phase_agents`). Losing the measure blocks promotion of that file.
2. **Joint (DSPy).** For each product, a `dspy.Module` with **five predictors** (one per
   `PhaseName`) is compiled with **`dspy.GEPA`** against the full-Build measure
   (`build_agents`). "DSPy" names the joint program; GEPA remains the optimizer so this
   does not silently substitute MIPROv2 or COPRO. Losing the joint measure blocks the
   **set** even if every individual file had passed.

Production Builds execute the promoted pinned files. They do not import `dspy`, do not
call GEPA, and do not fetch vendor docs.

**Dependency**: optional extra `prompt-tune` = `harness[evals]` + **`dspy==3.3.0`** (MIT;
install the real PyPI name `dspy`, not the `dspy-ai` compatibility alias). Scripts live in
`evals/prompt-tune/` and are not part of the served import graph. A unit gate fails if
`src/core`, served `src/adapters`, or `src/surfaces` import `dspy` or `gepa`.

If the extra is missing, `promote_phase_agents` / the promotion CLI refuses
`refinement_unavailable` rather than promoting unrefined text. License allowlist is a
merge gate: a GPL-family transitive means the extra does not land (do not weaken
`licenses/allowlist.txt`).

**ADR-0071** (implement writes it): prompt-optimization libraries are eval-lane / operator
machine only, analogous to `infra/bin` corpus-sync — not a new served egress class, not a
core/adapter import, model calls go through the existing eval broker (ADR-0058).

**Rationale**: Spec assumptions name GEPA then DSPy. Principle I forbids an agent framework
in core (ADR-0001). Principle VIII forbids executing unpinned optimizer output mid-run.
AGENTS.md forbids a casual core dependency.

**Alternatives considered**: MIPROv2 / COPRO / hand-edit "or equivalent" (forbidden by
named-contract rule). Putting `dspy` in `evals` extra (pulls a compiler into fixture
`make evals`). Putting `dspy` in `adapters` extra (served allocations would import an
optimizer they must never run). Calling vendor SDKs with a new key (Principle IV).

---

## R6 — Promotion and "unpromoted"

**Decision**: New function **`promote_phase_agents`** in `core.evals.promotion`, same three
independent checks as `promote_skill`: provenance (digest matches recorded bytes; authored
files use the provenance sibling + authorship date, not a fake upstream commit),
injection lens, evals.

Required suites for an authoring pack's instruction set:

- `PHASE_AGENTS_QUALIFICATION = "phase_agents"` — individual; must include at least one
  case per phase that a bad instruction loses (ADR-0047 / SC-004).
- `BUILD_AGENTS_QUALIFICATION = "build_agents"` — joint; must include at least one case
  the five lose together.

These are **not** members of `SUITES` (per-pack Ask suites). Same shape as
`AUTHORING_QUALIFICATION`: required of packs that declare an authoring workflow.
Case files live at `packs/<pack>/evals/phase_agents.toml` and `build_agents.toml` but
**must not** be loaded by `load_pack_cases` / `parse_cases` (those refuse unknown
`SUITES` names, and `test_eval_gates` asserts every `SUITES` member all-green). Named
loaders: `core.evals.phase_agents_corpus.load_phase_agents_cases` and
`load_build_agents_cases`. Adding these names to `SUITES` is a defect.

**Set promotion, not per-file copy.** If any one phase loses GEPA **or** the five-predictor
DSPy program loses `build_agents`, **none** of the five files are copied into `packs/` and
no `[[agents]]` digest is updated. Partial sets are forbidden.

Runtime "unpromoted": the only files an allocation executes are those whose digests are in
the deployed `pack.toml`. Candidates live under `evals/prompt-tune/candidates/` until
promotion copies **the whole set** into `packs/<pack>/agents/` and updates the pin. A
digest in the manifest without both qualifications in `suites_passed` is refused at
promote time; a missing pin is refused at load/phase start (`agents_missing`). There is
no `promoted=true` boolean that can be set by hand without the function.

Authored provenance: Terraform phase files are **authored** content inside an adopted pack
(they are not in `hashicorp/agent-skills`). Vault files are authored in an authored pack.
`promote_skill`'s `upstream_commit` requirement does not apply; `promote_phase_agents`
requires a non-empty `PROVENANCE.md` naming sources and authorship date instead.

**Rationale**: ADR-0004 three checks; 037/038 already taught not to stuff role-specific
corpora into `SUITES`.

**Alternatives considered**: Git merge equals promotion with no function (uncheckable).
`promoted` flag in TOML (can be flipped without evals). Requiring `upstream_commit` for
authored files (would invent a commit).

---

## R7 — Eval case shapes that can fail

**Decision**:

Hermetic / merge-blocking (deterministic; no live model):

- Binding: terraform research digest appears on the run; vault research digest does not.
- Fail-closed: omit Write `AGENTS.md` → Write fails, no PR.
- Isolation: terraform research body ≠ vault research body (substring / digest).
- No fallback: omit pack file, plant root `AGENTS.md` and a SKILL.md — still
  `agents_missing`.
- Ask: answering path never reads `packs/*/agents/`.
- Pin: mutate bytes without digest update → `digest_mismatch` at load.
- Suite floors: `phase_agents.toml` / `build_agents.toml` are parsed **only** by
  `load_phase_agents_cases` / `load_build_agents_cases` in
  `src/core/evals/phase_agents_corpus.py` (not `parse_cases`). `phase_agents` has **≥5
  cases per phase** and **≥1 fail case per phase**. `build_agents` has **≥5 cases** and
  **≥1 fail** for a jointly poisonous set. Scoring those fixtures must be able to report
  fail (ADR-0047). Fixture scoring uses recorded outcomes / mechanical properties
  (existing authoring corpus style), never a live model. `test_eval_gates` must not
  iterate these suite names.

Eval / named-runner (statistical; SC-006):

- After promotion, full Terraform and Vault Builds show a **strictly higher** pass rate
  than the generic pre-feature steer on `evals/authoring` golden tasks, same n. The
  named-runner README records n, both rates, and a positive delta.

**Rationale**: `docs/development/testing.md` — tests vs evals never mix.

**Alternatives considered**: Assert "the model wrote good HCL" in unit tests (forbidden).
Suites with only happy paths (SC-004 / ADR-0047).

---

## R8 — Authorship of published practice

**Decision**: Implement authors each `AGENTS.md` from current public HashiCorp
documentation and style guidance **at authorship time**, and records those sources plus
the date in `PROVENANCE.md`. That research is not a runtime tool and not an MCP fetch.
Restricted and air-gapped profiles execute the same bytes. Updating practice is a new
version: rewrite, provenance, lens, GEPA, joint DSPy, `promote_phase_agents`.

Bodies must be phase-and-product specific (SC-001): Terraform Write names modules, state,
variables, secrets handling, and anti-patterns; Vault Write does not instruct Terraform
resources; Research is not Write with the tools changed (FR-003).

**Rationale**: Spec US3, FR-006–008, ADR-0004, ADR-0030, Principle VIII.

**Alternatives considered**: Live web search during Research (air-gap lie). Empty templates
(US3 fails). Copying SKILL.md into AGENTS.md (FR-016 / FR-003).

---

## R9 — Evidence keys

**Decision**: Extend `content_pins` (and the `RUN_START` payload it feeds) with

```text
{pack}/agents/{phase}@{version} = <digest>
```

for every bound phase instruction the run actually started. The key carries identity
(pack, phase) **and** version (FR-012); the value is the executed digest. Correlation ID
is unchanged.

Do not log instruction **bodies** in audit (volume and injection surface). Identity,
version, digest, phase, pack name.

**Rationale**: FR-012, Principle IX, existing `pack@version` and `pack/skill` keys.

**Alternatives considered**: `{pack}/agents/{phase}` → digest only (drops version from the
joinable record). Hash only the pack version (cannot tell which phase file). Store full
prompt text in Postgres (bodies are large and not needed for reconstruction if the pin is
in git).

---

## R10 — Sealed-core blast radius

**Decision**: Allowed core edits are the pack pin/load/promote seam and
`ChoiceRequest.instruction` plumbing. Product strings stay out of `src/core`. Adapter
changes are concatenation only. Portal/Ask: no composition. Security-maintainer review
for those seams (Principle V). Named reviewer: Dan.

**Rationale**: Spec sealed-core paragraph.

**Alternatives considered**: Hardcoding terraform hints in `model_chooser` (caught by
product-blindness if moved to core; still wrong in the adapter). New portal API for
prompts (FR-013).

---

## R11 — 013 loader list is amended, not forked

**Decision**: `specs/013-capability-packs/contracts/pack-manifest.md` declared its load
sequence **closed**. 049 adds `[[agents]]` verification on that same sequence (skills
digests then agents digests/completeness for authoring packs). Implement **surgically
edits** that 013 contract: expand step 2 to cover skill **and** `AgentPin` digests, add
authoring-pack completeness after step 2, and replace “this list is closed” with “closed
except as amended by a later feature's pack-manifest contract — 049 amends it here.”
049's `contracts/pack-agents.md` is the amendment text; 013 must not keep claiming an
unamended closed list after 049 merges.

**Rationale**: Named contracts bind; two merged documents that disagree are a review
blocker (AGENTS.md).

**Alternatives considered**: Leave 013 untouched (silent conflict). Duplicate the full
loader contract only under 049 (readers of 013 would still be wrong).
