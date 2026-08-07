# Conformance: The admin console (044)

Rows **C1–C25** (hermetic unless marked), plus live legs **CL1–CL3**. Blocking from the moment
the feature exists (ADR-0047); none may be stubbed green.

**Named runner (constitution v1.1.0)**: the `enclave`-marked rows and the CL legs are run by
**Dan, before merge**, outcomes recorded here in the implementation PR.

## The write path exists and is governed (US2 — FR-005–008, FR-023/023a, SC-002/003)

| Row | Asserts |
| --- | --- |
| C1 | A change request is validated against the record's own parser before the fabric is asked; an unqualified cell refuses `unqualified_cell` with zero fabric writes (FR-009) |
| C2 | The three outcomes are distinct, and **pending is not applied**: a queued change alters no behaviour, and the row fails if the outcomes are collapsed (SC-003) |
| C3 | `wrap_info` is read by truthiness, not membership — driven with the present-as-null shape 007 found |
| C4 | A refused change is reported as refused and recorded with its requester (022: a refusal records) |
| C5 | Where no quorum is configured, an applied change carries the **ungated disclosure** (FR-007/023b) — the dev estate must not look like a governed one |
| C6 | Unit scan: every record the console can write appears in `controlled_paths` — completeness against the module's own list, 042's V6 shape (FR-023a) |
| C7 | A stale `cas` answers `record_moved`, never a silent overwrite (R9, US5) |
| C8 | The console holds no apply path: the only write reaches the fabric through the submitter, and the submitter maps outcomes — it never retries a refusal into success |

## Reading (US1 — FR-001–004, SC-001/004/005)

| Row | Asserts |
| --- | --- |
| C9 | An administrator's read returns the fabric's records as they are — compared field-for-field against the records the row wrote |
| C10 | An unreadable record renders **unavailable**, never empty or default (FR-002) |
| C11 | [no-secret-leak] No credential, key, or token value in any console response — asserted over the rendered payloads, including connection records |
| C12 | Every read is recorded with the administrator's identity (FR-004) |
| C13 | A non-admin is refused and the refusal recorded; `operator` and `compliance-analyst` do NOT see the console (FR-016a's one direction) |
| C14 | `admin` confers **no** audit visibility (FR-016a's other direction) — an admin's evidence read refuses exactly as a stranger's does |

## The toggle (US3 — FR-010–013, SC-006/011)

| Row | Asserts |
| --- | --- |
| C15 | Disabled: the answer still answers and carries the disclosure in its rendered response — not only in the record (FR-011) |
| C16 | The record distinguishes `relevance_disabled_by_admin` from `relevance_unavailable` (FR-012), and **no MODEL_GATE is written** for a gate that did not run |
| C17 | Re-enabled: the next ask judges, with no restart (FR-013/SC-011) — both states driven in one process against one surface |
| C18 | Absent field = enabled: every pre-044 binding record keeps its meaning |

## The exclusion (US4 — FR-014/015, SC-007/008) and the role (FR-016/017, SC-009)

| Row | Asserts |
| --- | --- |
| C19 | A dispatched run cannot reach configuration read or write: no tool resolves to them, and a planted instruction naming the console records an attempt and changes nothing |
| C20 | **The safety case can lose**: with the exclusion removed (the rigged-on construction), C19's scenario succeeds and this row fails (SC-007) |
| C21 | The console refuses a claim-mapping request granting `admin` to the requester's own subject (`self_grant_refused`, SC-009) — driven in several wordings of "own subject" |
| C22 | MCP's operation table contains **no configuration verb** (Q1) — the absence as a checked fact |

## Product connections (Q4 — FR-018a–c, SC-013)

| Row | Asserts |
| --- | --- |
| C23 | A connection change rides the same three-outcome path as every other record |
| C24 | Verification is its own fact: a fabric-accepted connection whose probe fails renders `unreachable`, never "applied and working" (FR-018c) |
| C25 | [no-secret-leak] No credential can be entered: the record's parser rejects fields outside the location vocabulary (FR-018b) |

## Live legs (named runner: Dan)

| Leg | What runs |
| --- | --- |
| CL1 **enclave** | The full request→decide cycle against the real Vault: submit under the API's attested identity, observe applied (dev, ungated, disclosed); with a quorum configured, observe pending and approve out of band — the mechanism has a principal for the first time (R1), and this proves it |
| CL2 **enclave** | The toggle end to end on a served surface: disable, ask, see the disclosure; re-enable, ask, see the gate — no restart |
| CL3 | `/settings` walked by the a11y suite (WCAG + keyboard/screen-reader), which today visits no console page (R10) |

## Out of scope, recorded

Approval UI (Vault's, by design); pending-change withdrawal beyond the wrapping token's own
TTL; consumption of `product-connections` by pack tool clients (the Terraform leg's work, and
the console labels it); any API-public or MCP verb.
