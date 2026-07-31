<!-- SPDX-License-Identifier: Apache-2.0 -->
# Conformance contract: 018 registry isolation

What these rows assert, what they refuse to assert, and who runs them.

---

## Who runs these rows

**Every row here is executed by an automated check** — `make conformance`'s `host_enclave`
line, which already enumerates `tests/conformance/authority/`. **No named human runner is
owed for the rows** (constitution v1.1.0, Quality Gates).

**The demonstration that the gate can fail is NOT a row.** It is a documented act, performed
once by a person against their own enclave, recorded below with its output. It grants a run
write access to its own ceiling, observes the row go red, and revokes it. That is deliberately
outside every lane: an automated fixture killed between grant and revoke would leave a real
control plane permissive with nobody watching, and a window that is small is not one that is
closed (FR-008).

The distinction matters and is easy to blur: *"no human runner owed"* is true of the rows and
false of the demonstration, and a contract that said only the first would be hiding the
second.

---

## The rows

| Row | Asserts | Requirement |
| --- | --- | --- |
| `test_a_run_cannot_write_any_bounding_record` | Every derived bounding path refuses a write under a real run's authority | FR-001, FR-005 |
| `test_the_refusal_is_attributable` | The same authority can **read** each path — so the refusal is about the capability, not a wrong path | FR-012 |
| `test_the_bounding_set_is_derived_not_listed` | The set comes from the deployed policy; a path added there is covered without anyone remembering | FR-006 |
| `test_a_permitted_write_is_its_own_outcome` | A write that succeeds reports distinctly and is undone | FR-004a, FR-004b |
| `test_ordinary_writes_are_not_in_scope` | A run's own space is untouched by this gate | FR-004c |

---

## What these rows do NOT assert

Stated as prominently as what they do, per ADR-0047.

- **Not that the bounding records are correct.** A ceiling granting too much, written through
  the reviewed configuration path, is invisible here. This asserts a *run* cannot change it,
  not that it is right (FR-011).
- **Not that writes through tools are refused.** A run calling a pack's write tool is the
  product working — the tool's own credential does that writing, in a different jurisdiction
  (ADR-0044). A run may spend the budget; it may not edit the budget. A gate that confused
  the two would forbid the platform's purpose while looking stricter.
- **Not that the read grant should exist.** These rows depend on it to attribute refusals.

---

## Known limits, recorded rather than closed

**Removing the run's read grant would fail every row.** Correctly — the refusal could no
longer be attributed — but at first glance it reads as though isolation had broken. The
failure message must distinguish *"the write was permitted"* from *"the refusal could not be
attributed"*, because those have opposite meanings and the same colour.

**`403` alone is not evidence, and this is not a subtlety.** Verified against the running
control plane on 2026-07-31: a mount that does not exist is refused in exactly the same words
as a real bounding record. Vault will not distinguish forbidden from absent — correctly,
since disclosing which leaks the tree's shape to an unauthorized caller. A row that read 403
as proof would pass with one letter wrong in its path, forever.

**The set is derived from what a run may READ, and then cross-checked against what exists.**
Every readable path in that jurisdiction is a bound it must not write, which makes derivation
sound — but the equivalence runs one way, and a record placed where a run cannot read still
bounds that run because the platform consults it regardless. So the derived set is compared
against the control plane's actual contents, and anything present but underived fails.

*Analysis found this.* The first design recorded it here as a known limit — "if one were
added the derivation would need revisiting" — which is a limit nobody would notice being
exceeded. FR-006a makes it a failure instead. 017 found the identical hole in its own coverage
mechanism after four passes: a scheme built from enrolments is blind to what never enrolled.

**The cross-check's jurisdictions are derived from the bounding paths**, not named. Two at
the time of writing — the authority store and the agent registry — and a bounding record
placed in a third extends the check without anyone editing it.

*Analysis pass 2 found this.* Pass 1 added the cross-check to close a fail-open hole, and
wrote its scope as "the control plane" — which is every mount, so the gate would have failed
on the first run, and which an implementer would sensibly narrow to the mount they thought of
first. That is the authority store. The agent registry — the record deciding whether a
definition exists at all — would have sat outside the very check added to make coverage
complete.

**What survives**: a bounding record held somewhere outside every derived jurisdiction —
another system entirely. Both halves are scoped to where the bounding paths already live, so
a bound outside all of them is outside both.

---

## SC-007: did anything stop running?

To be completed when the feature lands: per-directory `pytest --collect-only -q` counts
compared against `main`, confirming no pre-existing directory lost rows.

---

## The one-time demonstration

To be completed at implementation. Must record: the grant made, the row's failure output, the
revocation, and **verification that the revocation took** (FR-008a). Whoever performs it is
responsible for leaving the platform exactly as they found it, and the record must show that
rather than assert it.
