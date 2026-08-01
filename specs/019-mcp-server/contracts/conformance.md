<!-- SPDX-License-Identifier: Apache-2.0 -->
# Conformance contract: 019 — the served MCP surface

What these rows assert, what they refuse to assert, and who runs them.

---

## Who runs these rows

**Every row here is executed by an automated check** — a new `host_enclave` lane over
`tests/conformance/mcp_served/`, which brings the served process up, drives it with a real
client over a real socket, and tears it down. **No named human runner is owed for the rows** — true of the rows and of nothing else
(constitution v1.3.0, Quality Gates).

**Two things here are not rows, and each needs a named person.** The constitution requires it:
a blocking row no automated check executes MUST have a named party responsible before merge.

**SC-006 and FR-015 are the pair an earlier draft missed** — *a person follows the written setup
from nothing and connects*. No row can evaluate followability, and SC-006 had been tagged onto
an automated reachability row, so nominal coverage read 100% while nothing assessed it. T034a
performs it and records the outcome here, including anything the person had to read source to
discover, because that is the criterion failing rather than an aside.

**FR-017's demonstration is the other, and is NOT a row.** It is a documented act, performed once by a person
against their own enclave and recorded below with its output: a client presenting a credential
that must be refused, observed being refused *by the core*. That distinction is the same one
018 drew, and blurring it would let "no human runner owed" — true of the rows — read as true of
the demonstration, which it is not.

**The lane must select this directory's markers.** 018 shipped rows no lane collected while its
contract said otherwise. `tests/unit/test_every_conformance_directory_is_run.py` now catches
both shapes of that, so this is a reminder rather than a risk.

---

## The rows

**Provisional, and knowingly stale.** `/speckit-tasks` has since run and three analysis passes
have added rows this table does not list — the correlation row, the session-isolation row, the
disconnect row, and the row that stops a later fixture from satisfying FR-016. **T038 replaces
this table with the rows as shipped**, and that is when it becomes what a reviewer holds the
change against. Until then it is a sketch, and is labelled as one rather than left to look
authoritative.

| Row | Asserts | Requirement |
| --- | --- | --- |
| `test_a_client_establishes_a_session` | A real client completes the handshake against the running process | FR-001, SC-001 |
| `test_the_operation_set_matches_the_other_surface` | Mechanically equal, not equal by inspection | FR-008, SC-002 |
| `test_the_served_process_is_assembled_from_real_parts` | Real collaborators, no substitutes, and it refuses to start without them | FR-002, FR-003, FR-004 |
| `test_an_operation_is_governed` | The call goes through the governed core | FR-005 |
| `test_a_refusal_comes_from_the_core` | The refusal is the core's, not the protocol layer's | FR-006, SC-005 |
| `test_three_failures_are_distinguishable` | Refused, unknown, and transport failure are three answers | FR-007 |
| `test_the_trail_names_the_caller` | The audit record's subject is the calling user | FR-009, FR-010, SC-003 |
| `test_two_callers_are_distinguishable` | Two subjects, two records, neither the server's | FR-011, SC-004 |
| `test_no_credential_is_refused_before_the_operation` | Refused at the boundary, not inside | FR-012 |
| `test_a_lapsed_credential_stops_authorizing` | The session survives; the operation is refused | FR-013 |
| `test_a_session_binds_to_one_subject` | Fixed at the handshake, never reassigned | FR-013a |
| `test_it_is_reachable_from_outside_the_platform_network` | A client not inside the platform's network connects | FR-014, SC-006 |
| `test_neither_process_takes_the_other_down` | Stop each; the other keeps serving | FR-015a, SC-008 |
| `test_the_contract_states_what_this_does_not_assert` | This file still records its limits | FR-018 |
| `test_no_conformance_directory_lost_rows` | Per-directory collection counts against the prior state | SC-007 |

---

## What these rows do NOT assert

Stated as prominently as what they do, per ADR-0047.

- **Not that a model chose anything.** This is the limit most likely to be misread, because the
  demonstration is more convincing than the feature is broad. A client attaches, governance
  runs, a refusal refuses, evidence is written — and the tool selection driving it is still a
  scripted round-robin (ROADMAP gap 0e). Nothing here is evidence that an agent made a
  decision.
- **Not that the transport's operations are correct.** Fifty-six existing rows assert that
  against the class. These rows assert that a client can reach them and that identity and
  governance survive the boundary. **An operation that is wrong in a way those rows accept is
  wrong here too, invisibly.**
- **Not that the platform is safe to expose.** It is one developer's enclave. No rate limiting,
  no quota, no exposure hardening is asserted because none is claimed.
- **Not the other two transports.** ADR-0033 names four. This makes the second real; parity
  still binds incrementally across implemented pairs, as 009 amended it to.

---

## Known limits, recorded rather than closed

**The reachability row proves reachability from where the lane runs.** If the lane runs on the
developer's machine, it proves what FR-014 asks. If it ever moves somewhere that shares a
network namespace with the platform, the row keeps passing and stops meaning anything. Whoever
moves it owes this contract an update — recorded because the failure is silent, and because
this feature exists because of a different silent one.

**A refusal must be attributable to the core, and proving that is harder than observing a
denial.** A protocol layer that refused on its own would produce an identical outcome to the
core refusing. The row must therefore distinguish *where* the refusal came from, not merely
that one occurred. **This is the same trap 018 hit** — a control plane answering identically
for *forbidden* and *absent* — and it is called out here so the row is designed for it rather
than patched after.

---

## SC-007: did anything stop running?

To be completed when the feature lands: per-directory `pytest --collect-only -q` counts
compared against the prior state, confirming no pre-existing directory lost rows. The total
rises because this feature adds rows, so only the pre-existing directories are the comparison.

---

## The one-time demonstration

To be completed at implementation. Must record: the credential used, the client's own output
showing the refusal, evidence that the refusal originated in the governed core rather than the
protocol layer, and the state of the platform afterwards.

Performed by hand against a developer's own enclave, never in a lane — the same posture 018
set, and for a weaker reason here (nothing is made permissive), but the same one: an act whose
point is that a person watched it happen is not improved by automating the watching.
