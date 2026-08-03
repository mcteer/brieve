<!-- SPDX-License-Identifier: Apache-2.0 -->
# Conformance contract: 031 — a real model drives a governed run

## Who runs these rows

| Group | Where | Needs | Status |
| --- | --- | --- | --- |
| Operator sees denials; issued/expired stay hidden; focus row updated as its docstring demands | `tests/component/test_operator_sees_denials.py` + updated `test_estate_focus.py` | Nothing | Planned |
| Estate-suite agreement row still passes untouched (span unchanged — measured) | existing row | Nothing | Planned (asserted, not edited) |
| Plan subject in the live lane | `tests/evals_live/test_gates_live.py` | Vendor credential | Planned; run with the lane |
| **The demonstration**: seed → 2 bounded runs → restore → prove | `infra/bin/model-run-demo` | Enclave + credential; ≤15 vendor calls, stated | **The deliverable** |
| Post-demo: trail read-back (TOOL_CHOSEN names the real model; credential ref; refusal recorded) | script output + a verification step in it | — | With the demo |
| Post-demo: operator asks "which runs were denied?" through the ask path and the answer cites the demo's refusal | script's final step (API ask as the operator) | — | With the demo |

## What these rows assert

- The visibility change is exactly two types; grants stay analyst-only; the change and its focus-row
  update land together.
- Plan evidence is scored under a plan subject — the cell's claim and its evidence agree (030).
- The demonstration's restore is proven by comparison to captured originals, and the choice lane
  still dispatches against fixtures afterwards.
- **Honest limit**: the merge gate reads `variables.tf` and cannot see a leftover Vault-side cell;
  the script's own compare-to-captured check is the enclave-state safety net, stated rather than
  over-claimed.

## What these rows refuse to assert

- Model quality beyond the suites' thresholds.
- Anything about `write`/`judge`/`summarize` cells.
- Sealed-core payloads (nothing changes).
