# Implementation Plan: A model says what to do, not only what to use

**Branch**: `spec/040-model-supplied-arguments` | **Date**: 2026-08-06 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/040-model-supplied-arguments/spec.md`

## Summary

020 put a model in the loop for *which* tool runs; every tool's arguments have been a platform
constant ever since — `_PROBE_ARGUMENTS`, *"a fixture affordance, and it always was."* This
feature widens the model's **answer** to a name and its arguments while changing nothing about
what a model may **do**: the platform still invokes, the bracket still wraps it, the same
authority decides. Three consequences are the actual work: the intent record must carry the
arguments or every model-driven run resumes with an empty request (R3); that makes the control
plane the first durable home of raw model output, against a redaction rule applied to every
invoke, so the break is argued and bounded to exactly one store (R5, R6); and the recording
format grows a second grammar without moving the four suites that prove model-driven runs work
(R8). Plus one guard this repository has now earned twice: a merge-blocking capability-inventory
row, because two features shipped tools registered nowhere behind green rows (R10).

## Technical Context

**Language/Version**: Python 3.12 (repo-pinned via `uv`)

**Primary Dependencies**: pydantic-ai (the chooser's agent — `output_type` widens from `str` to a
structured choice), psycopg (Postgres durability), no new dependencies

**Storage**: Postgres (`intents` gains a nullable `arguments` column, additive) and the in-memory
provider (no change needed — which is itself a hazard, R3)

**Testing**: pytest — hermetic conformance rows in `tests/conformance/` (merge lane), component
rows in `tests/component/`, unit ledger row in `tests/unit/`; one enclave-marked row

**Target Platform**: the dispatched run allocation (Nomad) and the hermetic CI lane

**Project Type**: platform core + adapter + surface change, no new service

**Performance Goals**: none stated; the serialised-size check is O(request) once per answer

**Constraints**: every existing recording byte-compatible (FR-010); every pre-feature record
revivable with its original behaviour (FR-011, R4); the trail gains nothing (FR-006)

**Scale/Scope**: ~9 source files, 1 SQL migration line, ~18 conformance rows, no new modules
except the capability ledger

## Constitution Check

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | Nothing new is built but a ledger. The chooser, the bracket, the registry and the recording all exist; this widens what flows through them. |
| II — Total Interception; One Governed Tool Layer | **Pass** | The shape of a governed step is unchanged: the model answers, the platform invokes, `invoke_tool` stays the sole entry. The rejected toolset design (R1) is what would have violated this, and it stays rejected with `GovernedToolset` recorded as caller-less. |
| III — Fail-Closed, In-Process Enforcement | **Pass** | A malformed object, an oversized request and an unusable name are all refused and re-asked within the existing bound; exhausting it ends the run in a recorded terminal state. Truncation — the fail-open shape — is forbidden by FR-007c. |
| IV — Zero Standing Credentials; Authority Per Task | **N/A** | No credential path changes. |
| V — Sealed Core, Versioned Seams | **Pass, three named touches** | (1) **Durability**: `intents` gains a nullable `arguments` column, additive, NULL meaning pre-feature (R4); threaded through the one `IntentRecord` constructor and all three Postgres column lists. (2) **Registries**: `register()` gains `max_request_bytes` with a platform default — additive keyword, existing registrations unchanged. (3) **Adapters**: `ModelChooser`'s answer widens; all four `Chooser` implementations are in-repo (R9). **The hook engine is untouched** — 040 has no programs, so the idempotency key stays exactly as it is (R2). All three carry security-maintainer review. |
| VI — Lean by Default | **Pass** | No new operated component, no new dependency, no new allocation content. |
| VII — Anti-Fragmentation | **Pass** | One request path, one enforcement point for size (central in `resolve_step_tool`), one durable store for the request. |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | **Pass** | No model is promoted and no cell changes. The `_SYSTEM` prompt changes for every model-driven run — the live lane exercises the same prompt the fixture lane replays, and no per-model branch is introduced (`harness-owns-model-vocabulary`). |
| IX — Evidence Over Claims | **Pass, and the absence is the evidence** | `TOOL_CHOSEN` still carries the name and nothing else; `PRE_DECISION` still carries hashes; `RUN_RESUMED` still carries counts. Rows assert each payload set rather than inheriting the rule (R5). The one durable home of the raw request is the control plane, argued under a no-secret-leak gate on 038's precedent. |
| X — The Decision Record Governs | **Pass** | ADR-0065 is why this is its own feature; ADR-0026's bracket is extended additively; ADR-0051's redaction rule is broken exactly once, in the one place resume requires, and the break is recorded. No new ADR owed: no new operated component, no principle amended. |

**Gate result**: **PASS — proceed to Phase 0.** One obligation travels: the retention of the
kept request must end up **stated** (FR-007b) — schema comment, field docstring, quickstart — and
the row asserts the *behaviour* (nothing expires it), never the prose.

## Project Structure

### Documentation (this feature)

```text
specs/040-model-supplied-arguments/
├── plan.md
├── research.md          # R1–R12, carried from 039 where independent, re-verified
├── data-model.md
├── quickstart.md
├── contracts/
│   └── conformance-model-supplied-arguments.md   # M1–M18
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
src/core/choice/
├── chooser.py            # the ANSWER widens: name + arguments. `record_choice` payload UNCHANGED
├── bounded.py            # carries the model's arguments to the invoke in place of the constant;
│                         #   retry covers malformed object + oversized request (R12, R7);
│                         #   `already_chosen` widens to name + kept arguments
└── recorded.py           # second grammar: first non-space `[` → JSON list; bare name = choice
                          #   with NO arguments; NOTHING's "-" sentinel serves both forms (R8)

src/adapters/model_chooser.py   # output_type → structured choice; _SYSTEM asks for name AND
                                #   arguments; NONE still works

src/core/registry/memory.py     # + max_request_bytes per registration, platform default (R7)

src/core/durability/schema.sql  # intents + arguments column, NULLABLE — NULL means pre-feature,
src/core/durability/types.py    #   {} means genuinely nothing (R4). Field docstring states
src/core/durability/postgres.py #   retention. THREE column-list sites, all carried (R3)
src/core/observation/bracket.py # the one IntentRecord constructor gains the arguments, from the
                                #   one caller that already holds them (engine.py:247)

src/surfaces/dispatch/entrypoint.py  # already_chosen carries (name, arguments); NULL-argument
                                     #   revival supplies the legacy constant (R4); the constant
                                     #   is retired from the ask path

tests/unit/capability_inventory.py   # the ledger + AST sweep (R10); run_program cites ADR-0065,
                                     #   authoring trio cites the successor feature
tests/conformance/choice/            # M-rows beside the suites they must not move
tests/component/                     # resume rows against BOTH providers
```

**Structure Decision**: no new modules except the capability ledger. The recording rows live in
`tests/conformance/choice/` beside the four suites they are forbidden to move, for the same
reason 039 put reachability beside parity: splitting them lets one be read without the other.

## Constitution re-check (post-design)

Re-evaluated after Phase 1. No verdict changed; one sharpened:

- **IX** — the design makes the trail's silence checkable rather than asserted: M9 pins
  `TOOL_CHOSEN`'s payload to its exact six keys, M9a pins `PRE_DECISION` to hashes, and the
  RUN_RESUMED counts-not-contents closure is asserted rather than inherited. The intent store's
  possession of raw values is bounded by M10/M11's removability-and-retention pair.

**The honest cost, stated once**: after this feature, a model's own words rest durably in the
control plane until something removes them. The clarification decided that posture — kept until
removed, retention policy owed to the administrative surface — and this plan's job is to make the
eventual policy safe to apply: removal of a **closed** bracket's arguments is proven harmless
(M10), and the one unsafe removal (an open bracket's) is named in the same row rather than
discovered by the policy's first user.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| **The chooser's answer widens** for every model-driven run, not only ones that need arguments | A tool's arguments are what the act *is*; a name-only channel automates nothing that takes input | **Toolset to the agent**: moves execution inside the model's turn, bypasses all four 031 properties (R1). **A parallel arguments channel** beside the name: two answers that can disagree about one act |
| **Raw model output rests durably** in `intents`, against the redaction rule applied to every invoke | Resume re-invokes; a hash cannot be re-invoked with (R5) | **Not keeping it**: every model-driven run revives with an empty request — the defect, shipped. **Trail**: the one place it can never be taken back from. **Re-ask on revival**: re-execution wearing observation's clothes |
| **A second recording grammar** | JSON carries commas; the comma grammar is load-bearing for four suites (R8) | **One widened grammar**: every existing caller moves. **Escaping**: fixtures nobody can read stop being checked |
| **A per-capability size bound** rather than one number | An authored file and a workspace name differ by five orders of magnitude; one cap either forecloses authoring or gives a path room for a file | **No cap**: unbounded model output kept indefinitely — indefensible beside the retention answer. **Central shape contracts**: ruled out by clarification Q1 |

None is a new operated component; no named-trigger ADR is owed.
