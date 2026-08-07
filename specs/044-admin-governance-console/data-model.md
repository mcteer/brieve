# Data Model: The admin console

Shaped by research R1–R12. Nothing here is stored outside the trust fabric and the audit
trail; the console holds no state of its own — a thin client in front of a fabric that
decides.

## GovernanceConfiguration (US1, FR-001–003)

What a configuration read returns. Assembled per request from the fabric; never cached.

| Field | Source | Rule |
| --- | --- | --- |
| `bindings` | `ask-bindings` | guidance/estate/relevance cells, with each cell's qualification status from the matrix |
| `relevance_enabled` | `ask-bindings` | absent = enabled (R4) — old records keep their meaning |
| `qualified_cells` | `model-matrix` | read-only context: what a binding MAY name (FR-009's vocabulary) |
| `protected_policies` | `protected-policies` | read-only display; not writable through the console |
| `connections` | `product-connections` | locations + per-connection `verification` (R5) |
| `gating` | quorum posture | `gated` / **`ungated`** — FR-007/023b's disclosure, computed from whether a Control Group answered on the last change or from the fabric's posture record |

- An unreadable record renders as **unavailable**, never empty (FR-002) — `ProtectedSet`'s
  fail-closed reasoning, applied to display.
- No field may carry a credential (FR-003); connection records hold locations only.

## ConfigChange (US2, FR-005–008) — generalises `ClaimMapping` through the same submitter

| Field | Type | Rule |
| --- | --- | --- |
| `record` | enum: `ask-bindings` \| `claim-mappings/<key>` \| `product-connections` | the closed set of console-writable records (R2); anything else refuses before the fabric is asked |
| `payload` | record-shaped | validated against the record's own parser **before** submission (FR-009: an unqualified cell refuses here) |
| `cas` | int | the version the administrator read (R9); a stale `cas` surfaces "the record moved" |
| `requester` | str | the authenticated subject; carried into the record as `set_by` (R9) |

**Outcomes** — the three-state vocabulary, never collapsed (FR-006, SC-003):

| Outcome | Fabric signal | Console rendering |
| --- | --- | --- |
| `applied` | 200, no `wrap_info` | applied — **plus the ungated disclosure when no quorum is configured** (FR-007) |
| `pending` | 200, truthy `wrap_info` | awaiting approval; shows the accessor and the wrapping token's expiry (native withdrawal, R11) |
| `refused` | 403 | refused, with the fabric's reason — never rendered as an error page |

007's lesson is load-bearing here: `wrap_info` is present-as-null on every response, so
truthiness, not membership, is the signal.

## AdminRole (US1/US4, FR-016–017)

Not a new mechanism — a third key.

- `ROLE_VISIBILITY["admin"] = frozenset()` — **disjoint** (Q2): no audit visibility by virtue
  of the role; a row asserts both directions (FR-016a).
- Granted via the existing gated claim-mapping route; the console refuses a mapping request
  whose `role == "admin"` and whose claim matches the requester's own subject (FR-017).
- Console routes require `admin` in the resolved subject's roles, the same check evidence
  reads make.

## GateToggle (US3, FR-010–012)

One toggle in the first cut, and its semantics are the template:

| State | Answer behaviour | Record |
| --- | --- | --- |
| enabled (or absent) | 043's gate runs unchanged | `MODEL_GATE` as today |
| disabled | judge skipped; answer carries the disclosure in `relevance_note` | disposition `relevance_disabled_by_admin` — distinct from `relevance_unavailable` (FR-012); **no** `MODEL_GATE` written (the gate did not run) |

In-flight answers complete under the configuration read at their start (edge case) — true by
construction, since the binding is read once per ask.

## ProductConnection (US2/Q4, FR-018a–c)

| Field | Type | Rule |
| --- | --- | --- |
| `product` | enum: `tfe` \| `vault` | the two named in the ask |
| `address` | URL | location, never credential (FR-018b) |
| `organization` / `workspace` | str | TFE only |
| `namespace` | str | Vault only |
| `verification` | enum: `verified` \| `unreachable` \| `unverified` | R5's probe result with its timestamp; **never folded into the change outcome** (FR-018c — accepted and reachable are different facts) |
| `consumed_by` | display note | "not yet consumed by dispatched runs" until the Terraform leg lands — FR-022's honest middle |

## Audit events (FR-004, FR-008)

- **Config read**: administrator + records viewed, on the EVIDENCE_READ precedent — evidence
  access is itself audited, and configuration is evidence of posture.
- **Change requested / decided**: requester, record, requested value (locations and cell
  names — never credentials), and the fabric's decision, including refusals (022's rule).
- Payload discipline per 038's `FORBIDDEN_PAYLOAD_KEYS` table: identities and outcomes, never
  secrets.

## Refusal vocabulary added

`config_unavailable` (FR-002), `record_moved` (stale CAS, R9), `unqualified_cell` (reused —
FR-009 refuses at validation with the matrix's own word), `not_an_admin` (console routes),
`self_grant_refused` (FR-017), `unknown_record` (outside R2's closed set).
