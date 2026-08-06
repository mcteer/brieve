# Data Model: A model says what to do, not only what to use

**Feature**: 040 | **Date**: 2026-08-06

Two entities widen, one gains a field, one is new. Nothing else moves — and the list of what does
**not** move is most of the design.

---

## Answer (widened — R1's entity)

What a model returns when asked what to do at a step.

| Today | After |
| --- | --- |
| `str` — one tool name, or `NONE` | a structured choice: tool **name** and its **arguments** |
| the entrypoint invokes with the platform constant | the entrypoint invokes with the model's arguments |

**The shape of a governed step is unchanged, and that is the whole point.** The model still only
*answers*; the platform still *invokes*; the bracket still wraps it. The four properties 031
built survive because nothing about the step moves: bounded retry validates before invoking,
`already_chosen` still governs a resumed step, `TOOL_CHOSEN` is still recorded per step,
`choose()` still returns an answer rather than a side effect.

**Four implementations, all in-repo (R9)**: `ModelChooser`, `RecordedChooser`, the harness's
scripted chooser, and the empty-recording default. All move in one change; SC-007 pins the
observable contract from outside.

**A capability that takes nothing**: the answer carries an empty argument map, which is a
legitimate answer and byte-equivalent in effect to today's behaviour (FR-012).

---

## Request (new — the feature's entity)

What a model states it wants done with the capability it named.

| Rule | Where enforced |
| --- | --- |
| carried to the capability **verbatim** — the platform does not interpret it | `resolve_step_tool` → `invoke_tool`, unchanged pipeline |
| bounded in serialised size by the named capability's `max_request_bytes` | centrally, in `resolve_step_tool`, before any invoke (R7) |
| over the bound: refused and **re-asked**, never truncated; the refusal carries size and bound, never content | the existing `refused` list and re-choice bound |
| malformed (not a name-plus-arguments object): re-asked within the same bound | the existing retry, widened (R12) |
| permission unchanged: the same authority decides, on the tool name, exactly as today | clarification Q1 — carry-through only |

**Three failures, three records (FR-009)**: malformed is *re-asked* (a choice failure), a
governance deny is *refused* (the hook pipeline's decision), a request the capability rejects is
*performed and failed* (`tool_error`, the engine's existing path). An operator told the wrong one
fixes the wrong thing.

---

## Intent (gains a field — R3's entity)

The durable statement of *"we were about to run X"* — which must now say *"with these."*

| Field | Today | After |
| --- | --- | --- |
| `tool_name` | the tool a model named | unchanged |
| `arguments` | **absent** | the request it named it with — **nullable, default NULL** |

**NULL is not empty (R4).** NULL means *recorded before this feature existed*; its first attempt
ran with the legacy platform constant, so its revival supplies that constant — repeating the act
that was actually attempted. `{}` means *genuinely asked for nothing*. The distinction is
schema-level, not a heuristic, and it is what makes FR-011 checkable.

**One constructor, three column lists.** The record is built in exactly one place
(`bracket_call`), from the one caller that already holds the arguments. Postgres reconstructs it
from explicit column lists in three places, where a defaulted field fails **silently** — and the
in-memory provider needs no change at all, which is why every resume row runs against both
(SC-003, `memory.py:29`'s own rule).

**Retention (clarified)**: kept **until something removes it**. Nothing in the platform expires
it, and that is stated — in the column's schema comment and the field's docstring — while the
row asserts the *behaviour*, never the prose.

**Removability (FR-007a)**: clearing `arguments` on a **closed** bracket changes nothing — resume
reads arguments only for pending steps, so accounting, key, and re-observation are intact. The
one unsafe removal is an **open** bracket's: its revival would re-invoke with nothing, which is
this feature's defect reintroduced by policy. A future retention control inherits that constraint
by name: *finished acts only*.

---

## Registration (gains a property — R7's entity)

| Property | Rule |
| --- | --- |
| `max_request_bytes` | per capability, platform default; a capability whose legitimate requests are larger raises its own |

**A property, not a contract.** It sits beside `risk_class` and `repeatable` — facts about the
capability declared where its handler is bound. What clarification Q1 ruled out is the platform
holding a *shape* contract and deciding malformed centrally; the capability still decides what it
can use.

---

## Capability inventory (new — R10's entity)

What the platform defines, against what a run can reach.

| Set | Contents today |
| --- | --- |
| registered | `echo`, `plan`, `apply`, `write` (fixtures); `vault_read`, `vault_write`, `terraform_plan`, `terraform_apply` (packs) |
| defined and unreachable | `run_program` (**deliberate** — ADR-0065), `read_subject`, `author_file`, `open_proposal` (**pending** — the successor feature, named and dated) |

**The ledger is the record; the sweep keeps the ledger honest.** A name in neither set fails the
merge-blocking row. The row's companion proves the check can lose, because a reachability guard
that cannot fail is the defect it guards against.

---

## What does not change, and each absence is load-bearing

| Unchanged | Why it matters |
| --- | --- |
| `TOOL_CHOSEN` payload — six keys, no more | the trail's no-model-output rule, asserted by row |
| `PRE_DECISION` — argument keys and hashes | `redact_arguments` still runs on every invoke |
| `RUN_RESUMED` — counts, never contents | the closure that keeps revival records clean |
| the idempotency key | no programs, so steps already key distinctly (R2) |
| the observer interface — `idempotency_key` only | observers never see the request |
| the hook pipeline and every authority decision | carry-through only (Q1, R11) — `HookContext` already carries arguments and nothing consults their values to decide anything, which is where that stays |
| the four recording-driven suites, byte for byte | FR-010, and they prove model-driven runs work |
