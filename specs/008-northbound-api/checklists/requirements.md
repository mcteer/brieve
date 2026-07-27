# Specification Quality Checklist: Northbound API

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-27
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- **FR-014 refuses a gate row on purpose.** ADR-0033's four-transport parity cannot be
  asserted by the first transport — parity is a property *between* surfaces, and with one
  there is nothing to compare. Claiming it would be exactly the passing stub ADR-0047
  forbids. What this feature owes instead is FR-012: making the comparison possible.
- **The audit read path is new capability, not an extended query.** Before this, evidence was
  written and never read through the platform. FR-010 exists because reading evidence is
  itself an auditable act — the integrity of an audit trail includes knowing who read it.
- FR-003 is stated absolutely because a single exception would become the integration path
  everyone uses. ADR-0033's wording is "no static API keys, on any surface, ever".
- Clarify (2026-07-27) settled what the surface actually is, which the first draft assumed
  without stating: **run lifecycle and evidence, not direct tool invocation.** A caller
  invoking a tool through the API would act beside the agent rather than through it — a
  second path to the governed core, which is the shape Principle II exists to prevent.
- It also settled that starting a run returns a handle rather than blocking. Runs are
  durable and long by design; an API that blocked until completion would contradict the
  feature that exists to let work outlive a process.
- Analyze (2026-07-27) found two CRITICAL issues, both now fixed in the planning artifacts.
  The evidence table required a `tenant_id` that `AuditEntry` had no field for and forbids
  extras, so nothing could have written the column — `AuditEntry` now carries it, **inside
  the hash chain**, because a column beside the chain would leave the field deciding who may
  see a record alterable without detection. And identity flows were placed in a transport
  module despite Principle V naming them sealed core; they now live in `src/core/identity/`.
- It also caught that `conformance-hermetic` excludes enclave rows **by path**, which would
  have broken the fork-safe CI lane on the merge commit once `tests/conformance/api/` held
  both kinds. Now excluded by marker.
- US3 was stale against its own clarification — it still described operations that invoke
  tools, which FR-007 forbids. **Third occurrence of the same pattern**: a decision corrected
  in the requirements while its restatement in a story went unswept. Every artifact was
  swept this time rather than only the ones the pass named.
- Analyze pass 2 (2026-07-27) found that **both of pass 1's fixes had consequences one layer
  out**, which is the more useful lesson than either fix. Adding `tenant_id` to `AuditEntry`
  created a required field whose only supplier was the API, leaving the adapter and the
  002–007 suites unable to start a run; core now resolves a configured default. And giving
  evidence-access records their own correlation ID removed the entanglement but made each
  record a chain of one — `seq == 0` takes the genesis hash — so it linked to nothing and
  could be deleted undetected, defeating the reason the record exists. Records now go on a
  stable per-tenant evidence-access stream, which is a third option neither earlier pass
  considered.
- Analyze pass 3 (2026-07-27) found that the per-tenant evidence stream — pass 2's fix —
  introduced a **contended chain**. `build_next_entry` reads then writes, which is safe for a
  run chain only because 005's single-writer lease guarantees one writer, a coupling nothing
  had recorded. A stream shared by every reader in a tenant does not have that property, and
  the same helper also refetches every prior entry on each write, unbounded. Position and
  link now happen inside the insert transaction.
- It also found SC-009a overclaiming: a hash chain detects modification and middle-deletion,
  **not truncation**. Deleting the newest records leaves the remainder internally valid, and
  that is the obvious move against a log of who read what. Closed with `audit_stream_heads`,
  which the evidence role has no grant on at all.
- Three passes, and the top finding each time came from the previous pass's remediation. The
  evidence-access record was designed four ways before one held. That is the honest cost of
  a mechanism whose failure modes are all silent.
- Analyze pass 4 (2026-07-27) found that the transactional append could not honour the seam
  it implements. `AuditSink.append(entry)` receives `seq`, `prev_hash`, and `entry_hash`
  already computed by the caller — 14 call sites, five in core — so its shape *is*
  read-then-write. A transactional store could only verify what it was handed (the race
  returns) or overwrite it (the caller's hash goes stale). `append_event` now assigns and
  returns; `append` and `build_next_entry` are removed rather than kept alongside, because
  the older function is the one people would reach for.
- Also: a recorded head with no reader makes truncation detectable and undetected.
  `verify_stream_integrity` reads it back from `make enclave-verify`; continuous verification
  is deferred to the service that will carry the resume sweeper, and recorded as deferred.
- Four passes. The audit seam was designed when there was one writer per correlation ID and
  nothing was persisted, and each pass has been discovering the same thing from a different
  angle: a durable, shared, contended stream is a different thing wearing the same interface.
