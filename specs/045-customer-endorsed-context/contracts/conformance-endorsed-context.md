# Conformance: Customer-supplied context (045)

Rows **E1–E25** (hermetic unless marked), plus live legs **EL1–EL3**. Blocking from the moment
the feature exists (ADR-0047); none may be stubbed green.

**Named runner (constitution v1.1.0)**: the `enclave`-marked rows and the EL legs are run by
**Dan, before merge**, outcomes recorded here in the implementation PR.

## Endorsement is the gate (US1 — FR-001–004, FR-021, SC-005/006/010)

| Row | Asserts |
| --- | --- |
| E1 | An endorsement rides the console's three-outcome path — a fourth record, not a second mechanism; the completeness scan covers `endorsed-sources` across the grant, the gate list, and the code's closed set (R7) |
| E2 | The record carries who, what, when; withdrawal and adoption record the same way (FR-002/017e) |
| E3 | A non-administrator's endorsement attempt refuses and records (FR-003) |
| E4 | **The safety case can lose**: content synced but NOT endorsed resolves nothing, and with the endorsement check rigged out, it resolves — this row fails (FR-021, 044's C20 shape) |
| E5 | Withdrawal zeroes citability for the next question, no restart (FR-004/SC-011 — 044's C17 shape, driven in one process) |

## Sync and pin (US2 — FR-005–007, FR-017/018, SC-004)

| Row | Asserts |
| --- | --- |
| E6 | A sync records what it took, its identity, when, and who triggered it (FR-017); and [no-secret-leak] the sync record and every audit event carry **identities and paths, never document content** (FR-023) — endorsed material is exactly what an administrator may have endorsed carelessly, and an append-only trail is the wrong place for it. Asserted over the payloads, 038's `FORBIDDEN_PAYLOAD_KEYS` shape |
| E7 | Content failing its digest refuses — a refusal, never a fallback, never an answer from unverified content (FR-007/SC-004) |
| E8 | A sync failure, an empty source, and a source with nothing citable are **three distinct reports** (FR-018) |
| E9 | An unreachable source does not prevent answering from content already synced (FR-006) |
| E10 | [no-secret-leak] No credential appears in any sync record or console rendering of a source; private-source material is referenced from the trust store, never entered (R6) |

## Detect, review, adopt (US3 — FR-017a/c/d, SC-014/015)

| Row | Asserts |
| --- | --- |
| E11 | Detection compares tips and **changes nothing**: with drift flagged and unadopted, answers rest on the adopted version and disclose its age (FR-017d) |
| E12 | The review presents added / removed / altered documents against the adopted version (FR-017c, SC-015) |
| E13 | A source that moves again before review is reviewed against what is currently upstream (edge case) |
| E14 | Adoption flips the answering content for the NEXT question and is recorded with who and when; declining or ignoring changes nothing (SC-014). The adopted change **includes a document added upstream**, and it becomes citable with no fresh endorsement — FR-002a's defining consequence, asserted rather than described |

## A run keeps its ground (US4 — FR-017f–h, SC-016/017)

| Row | Asserts |
| --- | --- |
| E15 | A run started before an adoption completes on its original version; one started after uses the new one — both in one process |
| E16 | **Across a resume**: a run interrupted before an adoption and resumed after it continues on the version it originally resolved — the checkpoint carries the pin, and re-reading is not re-resolving |
| E17 | Every run and ask record names exactly one content identity (FR-017h) |

## Citing and disclosing (US5 — FR-008–011, SC-001/002/002a)

| Row | Asserts |
| --- | --- |
| E18 | A question only customer documents answer is answered, citations resolving against the synced copy by the same check the pin uses (FR-008, SC-001); and a path in **neither** pin does not resolve — every citation resolves against a recorded pin or not at all (FR-013) |
| E19 | Every citation carries `provenance` **as data**; an answer resting on customer material discloses it, and a mixed answer names both while each citation says which (FR-009/009a/010/010a, SC-002/002a) |
| E20 | A document with no addressable sections is not citable and is reported as such — never cited as a whole (FR-011) |
| E21 | The age disclosed for endorsed content is the adopted version's, by the pinned corpus's own rule (FR-017b) |

## Nothing weakens, nothing widens (US6/US7 — FR-012–016, FR-019/020/023, SC-003/007/008/009)

| Row | Asserts |
| --- | --- |
| E25 | **Tenant scoping does something** (FR-019): tenant A's endorsed content resolves nothing for tenant B's view. Cheap and hermetic in a single-tenant enclave, and the hook ADR-0046 will need — a key that is never exercised is a key nobody can trust |
| E22 | The pinned corpus loads, verifies, and declines exactly as before; the existing answering and citation rows pass **unedited** (diff row from the merge-base, `origin/<base>` fallback — third use of 043's lesson); an invented citation declines as before (SC-008/009) |
| E23 | **Zero outbound requests during answering** — asserted by instrumentation on the answering path with an endorsed source configured, not by absence of code (SC-003) |
| E24 | A dispatched run cannot endorse, adopt, or withdraw — no tool resolves to any of it, a planted instruction records and changes nothing, and the rigged-on construction fails this row (FR-020/SC-007); the authoring path consults the same synced copy and its proposal carries the disclosure (FR-015/016, SC-012) |

## Live legs (named runner: Dan)

| Leg | What runs |
| --- | --- |
| EL1 **enclave** | End to end against a real repository: endorse from the console → sync into Postgres → ask a question only that content answers → citations resolve, provenance rendered, age disclosed |
| EL2 **enclave** | Drift for real: change the upstream, watch the checker flag it, review the difference, adopt, and see the next answer move while a run started pre-adoption finishes on the old version |
| EL3 | The console's endorsed-sources page walked by the a11y lane (the 044 lesson: a page the lane does not visit is a page it has not tested) |

## Out of scope, recorded

MCP-server sources (the ROADMAP's own split); retention of superseded versions (deferred with
reasoning, R3); cross-tenant serving isolation (ADR-0046's feature — the tenant key exists, the
wall is not this feature's); content vetting of any kind.
