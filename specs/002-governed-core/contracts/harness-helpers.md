# Contract: Test harness helpers (public API)

**Feature**: `specs/002-governed-core`
**Audience**: Contributors writing governance tests; reviewers of semver seams
**Stability**: **Public API under the semver promise.** Names below are the contract
(FR-012). Renames require deprecation consistent with other versioned seams.

**Import path**: `from tests.harness import …` — the path is part of the public
contract. Packaging the harness as an installable distribution for operators (who
need these fakes to test their own hooks and packs per
docs/development/testing.md) is deferred: the interface is stable now; the
distribution mechanism arrives with the extension-authoring features. Moving the
import path later is a MAJOR seam change and rides the deprecation process.

## Required assertion helpers (exact names)

Imported from `tests.harness` (package export surface documented in
`tests/harness/README.md`):

| Helper | Asserts |
| --- | --- |
| `assert_denied_closed(result, reason=...)` | Outcome is deny; fail-closed path (not a soft skip); optional reason code match |
| `assert_correlated(audit, spans, run_id)` | One correlation ID joins audit entries and hook-decision spans for the run |
| `assert_audit_chain(audit)` | Append-only, hash-chain intact, no gaps |
| `assert_no_secret_values(audit, spans, model_context=...)` | Fixture secret markers / forbidden raw values absent from audit, spans, and optional model context |
| `assert_no_side_effect(target)` | Zero executions against a counter-bearing fake or registered-handler call counter; the 002 form is counter-based (the `fake_product_api` form arrives with later features) |

## Required supporting fakes (002)

| Fake | Role |
| --- | --- |
| `scripted_agent` | Emits a fixed sequence of tool calls (no live model) |
| `capture_audit` | In-memory audit sink with chain verification access for tests |

## Recommended for SC-006

| Helper | Role |
| --- | --- |
| `assert_hook_order(spans_or_probe_log)` | Governance capability / hooks observed before non-governance on the call |

(Documented in TESTING.md; implement in 002 so order is not asserted via private
engine internals.)

## Invariants

1. Helpers fail the test (raise `AssertionError`) when the property does not hold —
   they must not warn-and-pass.
2. Helpers do not call live models or product APIs.
3. Fixtures MUST NOT embed plausible real secrets; use obvious harness markers only.
4. `tests/harness/README.md` lists the shipped names and matches this contract.

## Out of scope for mandatory 002 delivery

`assert_scope_narrowed`, full `fake_identity_fabric`, durability fault helpers — may
appear as stubs or omit until 003+ unless trivial.

## Related

- [docs/development/testing.md](../../../docs/development/testing.md)
- [../spec.md](../spec.md) — FR-012, FR-013, US5
