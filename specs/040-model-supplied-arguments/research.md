# Research: A model says what to do, not only what to use

**Feature**: 040 | **Date**: 2026-08-06

Carried from 039 where its findings were independent of code mode (ADR-0065 superseded the
feature, not the measurements), re-verified against merged main today, and extended where the
clarifications changed the shape. Every entry is measured, not inferred.

## R1 — The gap is one constant, passed everywhere

**Measured**: `_PROBE_ARGUMENTS = {"path": "conformance/probe", "cas": 0}` at
`src/surfaces/dispatch/entrypoint.py:68`; passed as `arguments=_PROBE_ARGUMENTS` at
`entrypoint.py:221` for **every** tool a model names. Its own docstring: *"a fixture affordance,
and it always was."* `ModelChooser` asks with `output_type=str` (`model_chooser.py:149`) and a
`_SYSTEM` prompt demanding *"EXACTLY ONE tool name … and nothing else."*

**Decision**: the model's answer widens to a **name and its arguments** — a structured choice as
`output_type`, `_SYSTEM` rewritten to ask for both, and `resolve_step_tool` carrying the model's
arguments to `invoke_tool` in place of the constant. The platform still invokes; the model still
only answers.

**Rejected (039 R7, carried)**: giving the agent a toolset. It moves execution inside
`agent.run_sync` and bypasses bounded retry, `already_chosen` re-observation honesty,
`TOOL_CHOSEN` per step, and `choose()`'s answer-not-act contract. `GovernedToolset` keeps no
production caller, recorded as an open gap.

## R2 — What 039 needed that 040 does not: the key is untouched

039 changed the idempotency key because a **program** made several calls inside one step and the
seam never advanced `step_index`. 040 has no programs: every model-directed act is its own step,
`run.step_index` advances in the entrypoint's loop, and `_idempotency_key`
(`engine.py:440`) already yields distinct keys. Its docstring argues arguments *out* of the key
deliberately — *"a retry of one step is the same step even if its arguments were re-serialised
differently"* — and that stays exactly right. **No hook-engine change. The sealed-core touch 039
took twice, 040 takes once.**

## R3 — Resume loses the arguments, and the fix threads through one constructor

**Measured**:

- `intents` is `(run_id, idempotency_key, step_index, tool_name, recorded_at)` —
  `src/core/durability/schema.sql:93`. No argument column.
- `already_chosen` is built `{intent.step_index: intent.tool_name}` (`entrypoint.py:814`) and
  consumed as a bare string (`bounded.py:147-148`).
- A pending step **re-invokes**: *"re-observation found [the effect] had NOT landed — so it runs
  again."*
- The `IntentRecord` is constructed in **four** places, and only one is on the effect path:
  `bracket_call` (`src/core/observation/bracket.py:41`), whose one caller is `engine.py:247` —
  which already holds the arguments; the two Postgres reads (`postgres.py:293`, `:323`); and the
  **synthetic no-tool intent** at `entrypoint.py:318`, written with `tool_name="echo"` for the
  terminal no-tool case and closed in the same breath. **That fourth site must pass `{}`
  explicitly** — it genuinely asks for nothing, and letting it default would write NULL on a
  post-feature record, corrupting R4's rule that NULL means *pre-feature* (the fifth pass on 039
  noted this constructor and this feature nearly dropped the note).
- Postgres reconstructs the record from an **explicit column list in three places**:
  `record_intent`'s INSERT, `open_intents`' SELECT (`postgres.py:293`), `closed_intents`'
  (`postgres.py:323`). A defaulted field fails **silently** in each — the model validates, the
  row loads, the arguments are empty — and `open_intents` is the one resume reads.
- `InMemoryDurabilityProvider` stores the record object itself (`memory.py:65`), so it
  round-trips a new field **for free**. `memory.py:29` names the trap: *"The two must agree here
  or a row proven against one says nothing about the other — and this is precisely the property a
  hermetic row would be used to prove."*

**Decision**: `intents` gains an `arguments` column and `IntentRecord` a matching field; threaded
through `bracket_call` from its one caller, with the synthetic intent passing `{}`; carried
through all three Postgres sites; and
`already_chosen` widens to carry the arguments beside the name, so a revived step re-invokes with
the model's request and consults no model. The resume row runs against **both** providers, and
that clause is the row (SC-003's "every store").

**Rejected**: a second store (*"a second store holding the same fact would eventually disagree
with it"* — the entrypoint's own argument for the name); re-asking the model (what
`already_chosen` exists to prevent); storing a hash (nothing to re-derive from).

## R4 — Pre-feature records: NULL is not the same as empty

**The clarification's edge case, made mechanical.** A run disrupted before this feature carries
intents with no argument information, but its first attempt **did** run with the legacy constant
— so a revival that supplied `{}` would repeat a *different* act than the one attempted.

**Decision**: the column is **nullable, defaulting to NULL**, and NULL means *recorded before
this feature existed*. Revival of a NULL-argument intent supplies the legacy fixed values exactly
as the first attempt used them; `{}` means *genuinely asked for nothing*. The legacy constant is
retired from the ask path and kept solely for this revival case, marked as such. That is FR-011's
"distinguishable from one that genuinely asked for nothing" — it is a schema distinction, not a
heuristic.

## R5 — Raw values rest nowhere today, and this feature breaks that exactly once

**Measured**: `redact_arguments` returns *"argument keys and content hashes — never raw values"*
(`src/core/redaction.py:11`) and `engine.py:101` applies it to every invoke before any record is
written. `record_choice`'s `TOOL_CHOSEN` payload is `run_id, step_index, attempt, model, named,
outcome` and its docstring argues the absence: *"no model output beyond the name. The model may
have read a secret out of a tool result, and an append-only trail is the one place that must
never be written to."* Two onward paths are already closed with reasons recorded: an observer
receives `idempotency_key` **only** (`bracket.py:88`), and `RUN_RESUMED` carries pending/completed
steps as *"COUNTS rather than contents."*

**Decision**: `intents` becomes the **first and only** durable store of raw model-supplied
argument values — a security decision recorded as one, on 038's precedent (`PROGRAM_SUBMITTED`
was argued under a gate, not slipped in as a field). Bounded: control plane not trail, read by
resume not exported, removable (R6). The trail, the spans, and `redact_arguments` are unchanged,
and rows assert the payload sets and the two closures rather than inheriting them. The cheap
regression to watch: widening the redaction to "pass through what resume needs."

## R6 — Retention: kept until removed, removable without damage, stated

**Measured**: nothing deletes intents. No `DELETE`, no purge, no TTL anywhere in
`src/core/durability/`; `record_result` inserts into `results` and never touches the intent row.
"Released with the run" was false of everything.

**Decision (clarified)**: kept **until something removes it**, stated plainly. A configurable
retention policy is **owed to the administrative surface** and not built here. What 040 builds is
the property that policy needs:

- **Removable**: clearing `arguments` from an intent whose bracket is **closed** changes nothing
  the platform relies on — resume reads arguments only for *pending* steps, so the accounting,
  the key, and re-observation are all intact. A row proves it by clearing and re-reading.
- **The one unsafe removal, named**: clearing an **open** bracket's arguments makes its revival
  re-invoke with nothing — the exact defect this feature fixes, reintroduced by policy. Recorded
  as the constraint a future retention control inherits: *finished acts only*.
- **Stated**: the column's schema comment and `IntentRecord`'s field docstring state the
  retention in words; the **row** asserts the behaviour (survives arbitrary time, nothing
  expires it) rather than matching the prose — this repository has caught six checks matching
  comments instead of code.

## R7 — The size bound rides the registry, and the refusal rides the re-ask loop

**Measured**: `register()` already carries per-tool properties — `risk_class`, `product_mode`,
`repeatable`, `observer` (`src/core/registry/memory.py:57-67`). Two size precedents exist:
`MAX_MESSAGE_BYTES = 8192` with a refusal that records *"the message's SIZE and never its
content"* (`threads/records.py:23`, `TURN_REFUSED`), and `READ_BUDGET_BYTES = 4 MiB`
(`authoring/tool.py:49`).

**Decision (clarified)**: `register()` gains `max_request_bytes` with a platform default
`DEFAULT_REQUEST_BYTES = 64 KiB` — sized generously above any structured request the current
tools take, well under file content. A capability whose legitimate requests are larger raises it
at its own registration (the authoring tools will, when 041 registers them — the read budget is
the order of magnitude). Enforcement is **central and single**: `resolve_step_tool` measures the
serialised request against the named tool's bound *before* invoking; over it, the answer joins
the existing `refused` list and the model is re-asked within `DEFAULT_RECHOICE_BOUND = 3`
(`bounded.py:51`) — never truncated, and the refusal reason carries the size and the bound,
never the content. No new `ChoiceOutcome` member: the existing refusal mechanism already carries
`(name, reason)` pairs, and a new audit vocabulary entry for a size refusal would duplicate it.

**This does not reopen the clarification's Q1**: a size is a *property of the capability*
declared beside its handler, like `risk_class`. What was ruled out is the platform holding a
contract about the request's *shape* — each capability still decides what it can use.

## R8 — The recording format: two grammars, chosen by the first character

**Measured**: `parse_recording` is `raw.split(",")` (`recorded.py:100-102`), the value arrives as
`RUN_CHOICE_RECORDING` from `NOMAD_META_choice_recording` (`entrypoint.py:442`,
`agent-run.nomad.hcl:241`), and JSON contains commas. **Five** conformance suites feed bare names
through recordings — `conformance/choice/harness.py`, `choice/test_a_model_chooses.py`,
`choice/test_the_double_is_faithful.py` (measured: `build_chooser(FIXTURE_MODEL,
recording=recording("vault_write", "vault_read"))` at line 66 — the suite 039's inventory
missed), `durability/test_model_driven_resume.py`, `reports/test_the_run_observes.py` — and the
`recording(*answers)` helper itself lives in **`tests/harness/scripted_chooser.py`**, not in
`choice/harness.py` as 039's carried note claimed. They are the rows that prove model-driven runs
work at all, and an inventory that undercounts them is a compatibility row that passes while the
uncounted suite is edited. `NOTHING = "-"` is spelled because *"an empty element in a comma-separated list is
indistinguishable from a trailing separator"* (`recorded.py:34`).

**Decision**: a recording whose first non-space character is `[` parses as a JSON list of
`{"tool": ..., "arguments": {...}}`; anything else splits on commas exactly as today, and **a
bare name is a choice with no arguments**. The JSON form spells the terminal answer with the same
`"-"` sentinel — one rule, both grammars. Two grammars is the honest answer because FR-010 *is*
that the old one keeps working; base64-style encoding was rejected because a recording is a thing
a person writes by hand, and unreadable fixtures are how a row stops being checked.

**And the empty-recording default is unchanged**: `RecordedChooser` with nothing recorded answers
`sorted(request.permitted)[0]` (`recorded.py:82`) — now with no arguments, which is the true
answer for the fixture tools and load-bearing for every pre-020 dispatched row.

## R9 — Chooser is a Protocol with four implementations, all in-repo

**Measured**: `Chooser.choose()` returns `str` today. Implementations: `ModelChooser`
(adapter), `RecordedChooser` (core), the harness's scripted chooser
(`tests/harness/scripted_chooser.py`, injected *at the binding, never at the loop*), and the
empty-recording default inside `RecordedChooser`. No third-party implementations exist.

**Decision**: `choose()` returns a structured answer (name + arguments), and all four
implementations move in the same change. The seam is versioned (Principle V — adapters are
sealed), the change is a widening with no external consumers, and SC-007 pins the observable
contract: every existing recording and scripted answer produces the identical result.

## R10 — The capability inventory: a ledger the check keeps honest

**Measured**: the platform defines five capability names in `core` outside the pack handlers —
`run_program` (`sandbox/program_tool.py:31`), `read_subject`, `author_file`, `open_proposal`
(`authoring/tool.py:37-39`), and the fixture `write` — and **four of the five are registered
nowhere**. `PLATFORM_HANDLERS` holds `vault_read`, `vault_write`, `terraform_plan`,
`terraform_apply`. Two features shipped this shape with green rows; both were found by accident.

**Decision**: a merge-blocking unit row backed by an explicit ledger:

- `DELIBERATELY_UNREACHABLE = {name: (reason, record)}` — `run_program` cites ADR-0065; the
  authoring trio cites *"unreachable pending registration — the successor feature"*, which turns
  a silent gap into a named, dated one that 041 must consume.
- The row asserts every ledger-listed and every registered name is accounted for **and** the
  ledger itself is complete: an AST sweep of `src/core` for module-level string constants
  exported and consumed as tool names, plus every literal passed to `registry.register` across
  `src/`. The sweep is the part that catches the *next* 038 — a constant the ledger never heard
  of fails the row.
- **Prove it can fail**: the row's companion removes a name from the ledger in-memory and
  asserts the check trips. A reachability guard that cannot lose is the defect it guards against.

**Residual, stated**: a capability defined in a shape the sweep does not recognise (not a
module-level constant, not a literal at a register call) escapes it. The convention is documented
in the ledger's own docstring; narrowing that residual is not worth a parser.

## R11 — Where the answer's arguments meet the hooks: nothing new decides

**Measured**: `HookContext` already carries `arguments` (`hooks/types.py:40`); the authority hook
decides on the tool name against the run's scope; `redact_arguments` hashes every argument set
into `PRE_DECISION`. Nothing consults argument *values* to decide anything.

**Decision (clarified)**: carry-through only. The pipeline is unchanged: model-supplied arguments
arrive at `invoke_tool` exactly as platform-supplied ones do today, every hook sees what it
already sees, and each capability enforces its own rules (038's containment lives in
`author_file`, and stays there). Argument-level policy is deferred with its absence recorded —
the machinery that would carry it exists and nothing consults it.

## R12 — What "malformed" means once the answer is an object

**Measured**: `resolve_step_tool`'s bounded retry (`bounded.py:146`) was written for an
unpermitted or unknown *name* — `is_tool_name` distinguishes *not a tool at all* from *a real
tool outside this ceiling* because *"those are different things to whoever reads the trail."*

**Decision**: the retry covers three new failure shapes, each distinguishable in the refusal
reason like the existing two: a **malformed object** (does not parse as name-plus-arguments), an
**oversized request** (R7), and a **valid object naming an unusable tool** (the existing paths,
unchanged). A request the capability itself rejects is **not** a choice failure — it is an
executed call that failed, decided by the capability, recorded as `tool_error` by the engine's
existing path (`engine.py:374` returns `decision="deny", reason_code="tool_error"`), and visible
to FR-009's three-way distinction: malformed (re-asked), refused (denied by governance), failed
(performed and failed on its own terms).

## R13 — The column arrives by the repository's own migration pattern, or not at all

**Measured**: `schema.sql:35-48` argues this in its own words. `CREATE TABLE IF NOT EXISTS` *"is
a no-op against an existing table — it does not reconcile columns"*, so on any enclave brought up
earlier the new column *"would simply not exist"* and every insert naming it fails — *"the whole
durability layer down, on a running enclave, from a file that looks like it declares the
column."* `resume_count` was *"the first additive column in the repository's history"* and set
the pattern: the column appears **twice** — in the `CREATE` declaration, where someone reads what
the table *is*, and as `ALTER TABLE intents ADD COLUMN IF NOT EXISTS arguments TEXT`, which is
idempotent and therefore safe for `migrate()` (`postgres.py:111`) to re-apply on every boot.

**Decision**: both lines, on `resume_count`'s precedent, with no default expression — existing
rows read back NULL, which is R4's *pre-feature* meaning arriving for free. The plan's "1 SQL
migration line" was an undercount; it is two, and the second is the deployment story.
