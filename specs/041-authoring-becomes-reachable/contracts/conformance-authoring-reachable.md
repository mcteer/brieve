# Conformance contract: authoring is reachable, and the suite can lose

**Feature**: 041 | **Lane**: merge-blocking (hermetic) plus enclave rows | **Runs on**: every PR
(hermetic); enclave lane per its own trigger

**Who runs what**: CI's fast lane runs every A-row. The E-rows run in the local enclave lane
and publish against a real repository, which CI cannot reach fork-safely. **Named runner: the
agent harness, driven by the maintainer (Dan McTeer), before merge** (constitution v1.1.0).
E-rows **fail rather than skip** when the enclave, the App installation, or the target
repository is unavailable (FR-016, FR-024) — `tooling_missing` and `lane_absent` are failures
with names, never skips.

**The stub most available here**: a reachability row that asserts the trio registered by
calling the registration function itself — which passes whether or not any production path
calls it. Every A-row below therefore drives the **entrypoint's** construction or the derived
vocabulary, never the registration function directly. 038's rows already cover the handlers'
behaviour; these rows cover the path to them.

## Reachability (US1)

### A1 — A ceiling naming the trio parses and resolves (FR-002, SC-001)
The same ceiling record refuses `unknown_ceiling_entry` against the pre-041 vocabulary and
resolves against the post-041 one. Both halves asserted — the row pins the *change*, not just
the end state. **The "before" is A4's rigged-off construction, in-process** — there is no
pre-041 tree to run in a single checkout (040's M3 named this trap), so the row and its
self-test deliberately share one seam.

### A2 — Three refusal layers, three distinguishable reasons (FR-019, SC-008)
Unknown tool / known-but-outside-ceiling / inside-ceiling-but-outside-task-scope: three runs,
three distinct reason codes, each naming the record an operator should read next. **The third
layer requires the refusal to name which intersection term excluded the tool** — today
`intersect_scopes` computes one effective set with no memory of which term dropped what, so
this row has a mechanism task (T002a), not only an assertion.

### A3 — Registration is the opt-in switch (FR-003)
A definition whose ceiling omits `author_file` has no authoring even though the registry knows
the name. Asserted through the entrypoint-built registry.

### A4 — The suite can lose (FR-018, US4)
A rigged entrypoint construction with the authoring branch disabled must make A1/A3 **fail**.
Runs as a self-test of the rows, not of the product.

### A5 — The ledger closes and re-arms (FR-015, SC-006)
The trio MOVES from `DELIBERATELY_UNREACHABLE` to the declared per-run-reachable record naming
the entrypoint's authoring branch as registrar — the static sweep cannot see per-run
registration, so a declaration carries it, and this row keeps the declaration honest: driving
the registering construction shows each declared name actually registers, and with the branch
rigged off the check FAILS. An entry in neither record fails `unaccounted()` as before.

## The governed path (US2)

### A6 — Same pipeline, same records (FR-004, SC-003)
An `author_file` call traverses the identical entry/hooks/records as `vault_write`; argument
provenance and risk class are the only diffs in the recorded shape.

### A7 — Workspace containment survives dispatch wiring (FR-006)
Escape paths refuse through the registered handler (resolved, not string-matched) — the row
drives the registered tool, not `FileAuthor` directly.

### A8 — Governed subject reads (FR-005)
The lens fires, the read is recorded, the budget refuses over-budget reads with disclosure, and
`consulted` enumerates in order — all through the registered `read_subject`.

### A9 — Task scope beats ceiling (FR-001, US2-4)
An analyzer-scoped run cannot call `open_proposal`; a proposer-scoped run cannot call
`author_file`. Both refusals carry the task-scope reason.

## Acquisition (FR-026–028, R3–R5)

### A10 — The subject is the target repository, by construction
`AcquiredSubject.path` is a checkout of `target_repository` at `commit`; the analyzer's mount
is that path; `subject_is_platform_tree` still refuses the platform's own tree. **A resumed
analyzer re-acquires at the recorded `commit`, never at HEAD** — two attempts of one run must
analyse one tree.

### A11 — Acquisition refuses before anything is produced (FR-028)
Unreachable repository, missing revision, exceeded bound: three refusals, three codes, no
workspace created, no run started.

### A12 — The bound is disclosed, never silent (R4)
An over-bound checkout refuses with the size named; the refusal carries no content.

## Publishing (US3)

### A13 — Idempotency by branch (FR-025, SC-010)
Two publishes with one idempotency key: one PR. The second run's result carries `reused=true`.
Hermetic via a fake forge seam; E2 proves it real.

### A14 — The observer resolves an interrupted publish (FR-010)
`CANNOT_DETERMINE` resolution queries the head branch and converges: existing PR → observed,
absent → created. No second proposal on any path.

### A15 — Token never persists (FR-023a, R9)
After a publish: no token under the task's `$HOME`, no `hosts.yml`, no token in `.git/config`
or remote URLs, none in the checkpoint, none in any audit payload. The subprocess env is
constructed per call.

### A16 — Description containment (FR-031, FR-032)
A rationale carrying a planted secret or analysed-content span refuses publish via the existing
containment path; a truncated artifact without a note refuses compose (exists — asserted
surviving through the production path).

### A17 — Suspension carries a product, and the product carries a probe (FR-029, FR-030)
`open_proposal` suspends against product `github`; the generic guard fails for any registered
suspendable tool with no product mapping. **And the probe attaches**: the health checker's
product→probe table includes `github` for an authoring run — asserted against the table the
checker actually consumes, because a probe in a dict nothing reads is the same defect as a
handler in a module nothing calls, one seam over.

### A22 — Kept requests are scrubbed at terminal state (FR-033)
An authoring run reaches terminal state; its kept model requests hold no subject-derived bytes
afterwards. Asserted against the durability store directly, both providers — the in-memory
provider round-trips scrubbing for free, which is exactly the shape 040's M7 exists to catch,
so the Postgres leg is the one that counts. A non-authoring run's requests are untouched:
scrubbing is scoped, not global, because 040's retention decision for ordinary runs stands.

## Qualification (FR-012, SC-011)

### A18 — Unqualified refuses distinguishably (exists as Q1; re-asserted through dispatch)
No qualified `write` cell → the dispatched run stops `unqualified_cell`, never
`provider_unavailable`.

### A19 — The bound cell is the estate's model (FR-012b)
The bound `write` cell names Sonnet 5 and carries ADR-0063 mechanical evidence, dated.

## Compatibility (US5)

### A20 — 038's rows unedited (FR-017, SC-005)
`git diff` over `tests/conformance/authoring/` limited to 038's files is empty; the suite
passes.

### A21 — Non-authoring runs unchanged
A definition naming no authoring tool: identical vocabulary, resolution and records before and
after — asserted by the unedited recording-driven suites.

## Enclave rows (named runner above; fail, never skip)

### E1 — The full cycle, real (SC-002, SC-009, FR-016)
A dispatched two-task run under attested identity: clone → read → author → contain → checkpoint
→ continue → publish. A real PR exists on the target repository; its file digests match the
artifact's; its description carries rationale + provenance; the trail walks end to end under
one correlation ID.

### E2 — Real idempotency (SC-010)
The same request re-dispatched: the PR count for the head branch is still one.

### E3 — The analyzer cannot publish, observed (FR-007, SC-004)
From inside the analyzer task, the credential read fails for want of an attested identity —
the structural absence, observed in the real allocation.

### E4 — Continuation consumes no resume attempt (FR-009)
The healthy handoff leaves the resume-attempt count untouched; `RUN_RESUME` is unset on both
tasks.
