# Conformance: The admin console (044)

Rows **C1–C26** (hermetic unless marked), plus live legs **CL1–CL3**. Blocking from the moment
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
| C9 | An administrator's read returns the fabric's records as they are — compared field-for-field against the records the row wrote; the payload's setting set is **exactly the implemented set** (FR-022 — absent, never disabled), and `qualified_cells` comes from the matrix and nothing else (FR-009's offer side) |
| C10 | An unreadable record renders **unavailable**, never empty or default (FR-002) |
| C11 | [no-secret-leak] No credential, key, or token value in any console response — asserted over the rendered payloads, including connection records |
| C12 | Every read is recorded with the administrator's identity (FR-004) |
| C13 | A non-admin is refused and the refusal recorded; `operator` and `compliance-analyst` do NOT see the console (FR-016a's one direction) |
| C14 | `admin` confers **no** audit visibility (FR-016a's other direction) — an admin's evidence read refuses exactly as a stranger's does |
| C26 | The role vocabulary the console presents is exactly ADR-0039's, asserted against the canonical constant (FR-018, SC-010) — a friendly alias added later ships a name the platform does not implement, which is the drift R7's decision exists to stop |

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

## Enclave run — 2026-08-07

Executed by the harness against the dev enclave, trust-fabric applied:

| Leg | Outcome |
| --- | --- |
| **CL1** request → decide | **pass.** `authority-submit` is attached to the api role — the mechanism has a principal for the first time since 007. Read binding v4 (`relevance_enabled` absent = enabled, `set_by` absent = an estate apply) → submitted disable → **applied, ungated** (quorum is null in dev) → read back v5, `relevance_enabled=False`, `set_by=console/dan` → stale CAS **refused** → restored. |
| **CL2** the toggle on a served surface | **pass.** Three real asks through the served MCP surface, gate flipped in the trust fabric between each, **nothing restarted**: enabled → `relevance to the question was judged by a model`; disabled → `relevance was NOT checked: an administrator has disabled the relevance gate…`; enabled again → judged. The disclosure reaches a real caller over the wire. |
| **CL3** a11y | **pass** — 72 rows, `/settings` walked in both the WCAG scan and the screen-reader tree. |

**CL1 found a defect no hermetic row could.** Vault answers a failed check-and-set with
**400** and `"check-and-set parameter did not match the current version"`, not 409. The code
checked for 409 and the hermetic row scripted a 409 — a test agreeing with its author rather
than with the product — so `RecordMoved` would never have fired against the real Vault and two
administrators would have overwritten each other silently. Now discriminated on Vault's own
message, with the unrecognised case falling through to `AuthoritySubmitUnavailable` (loud, and
they retry) rather than the reverse.

**CL2 first ran against a three-hour-old allocation and read as a failure of the feature.**
The served payload carried no `relevance_note` key at all — not an empty one — because
`mcp-surface-up` submits the job and Nomad places no new allocation when the jobspec has not
changed. The running process predated every 044 commit. Replacing the allocation was the whole
fix, and the lesson is that "deployed" and "running the code you just wrote" are different
facts: an absent KEY rather than an empty value is the tell, and it is worth checking before
concluding the code is wrong.

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
