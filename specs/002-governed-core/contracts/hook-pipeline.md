# Contract: Hook pipeline

**Feature**: `specs/002-governed-core`
**Audience**: Core implementers, adapter authors (later), conformance tests
**Stability**: Behavioral contract is sealed-core; symbol names may refine in `feat/002`
but must preserve the invariants below.

## Entry point

```text
invoke_tool(run: GovernedRun, tool_name: str, arguments: Mapping) -> InvokeResult
```

There is **no** supported API that executes a registered tool handler while skipping
pre-hooks (FR-001).

## Pipeline order (normative)

For each `invoke_tool` call:

1. **Refuse** if `run` is not active / has no correlation ID.
2. **Registry resolve** — failure or missing name → **deny** (no body); audit + span.
3. **Scope check** — `tool_name ∉ run.scope` → **deny** (no body); audit + span.
4. **Pre-hooks** — all `capability_kind=governance` hooks, then `other`, in stable
   registration order within each kind.
   - Any deny decision → **deny** (no body).
   - Any exception / corrupt decision → **deny** (FR-006); never allow.
5. **Execute** tool body **at most once** if and only if all pre-hooks allowed.
6. **Post-hooks** — same governance-first ordering — run if execution was attempted,
   **including when the tool body raised** (FR-015).
7. **Post-hook failure** after execution → outcome recorded as failed/denied-closed
   post-path; audit MUST still show the tool executed (spec edge case).
   A post-hook failure short-circuits any remaining post-hooks; this is acceptable
   because the outcome is already failed-closed — later post-hooks cannot convert it
   back to success, and their skipped observations are covered by the recorded failure.

## InvokeResult (logical)

| Field | Meaning |
| --- | --- |
| allowed | Whether the call completed as an allow path (tool ran and post-path did not fail closed) |
| decision | Final effective decision (`allow` / `deny`) |
| reason_code | Stable code (`unregistered`, `out_of_scope`, `hook_deny`, `internal_error`, …) |
| message | Safe user-facing text (FR-014) |
| correlation_id | Echo of run correlation ID |
| executed | Whether the tool body ran |

**Known future tightening**: distinct `unregistered` vs `out_of_scope` reason codes
disclose tool existence to an out-of-scope caller. Acceptable in 002's single-run
model; when multi-tenancy lands (ADR-0035/ADR-0046 — denial must not disclose
existence), these codes are expected to collapse to one externally visible code with
the distinction preserved in audit only. Callers MUST NOT build logic on the
distinction being externally visible.

## Ordering observability

Tests MUST be able to observe hook invocation order (probe hooks or spans) and assert
governance-before-other (FR-011, SC-006). Reversing registration must not invert
governance-first sorting.

## Invariants

1. In-process only — not delegated to gateway/mesh as load-bearing control (ADR-0006).
2. Fail closed on enforcement-path errors (FR-006).
3. Correlation ID on every decision and span for the call (FR-007, FR-009).
4. No secret values in decisions, spans, or logs (FR-010).
5. An action that cannot be audited does not proceed: audit-append failure during the
   pre-execution path denies the call (reason `internal_error`) and sets the
   evidential-gap flag — a denial that could not be recorded is also an evidential gap.
   Audit-append failure on the post-execution path records the outcome as failed-closed;
   if even that record cannot be written, the InvokeResult MUST report the evidential
   gap — the call never reports clean success with an incomplete trail.

## Related

- [../spec.md](../spec.md) — FR-001–FR-007, FR-011, FR-015
- [../data-model.md](../data-model.md) — HookDecision, GovernedRun
- ADR-0006, ADR-0019
