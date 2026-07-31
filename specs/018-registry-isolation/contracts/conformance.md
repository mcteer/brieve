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
closed (FR-017).

The distinction matters and is easy to blur: *"no human runner owed"* is true of the rows and
false of the demonstration, and a contract that said only the first would be hiding the
second.

---

## The rows

| Row | Asserts | Requirement |
| --- | --- | --- |
| `test_a_run_cannot_write_any_bounding_record` | Every **derived** bounding path refuses a write under a real run's authority | FR-001, FR-010 |
| `test_a_run_cannot_write_the_grant_itself` | Every **named** bound refuses — the ceiling grant, what decides which grants a run receives, the trusted-key configuration | FR-001, FR-016 |
| `test_a_refusal_is_attributable` | The same authority can **see** each path, so the refusal is about the capability and not about a path that is not there | FR-006 |
| `test_a_typo_in_a_path_does_not_pass` | One letter wrong reports *unattributable*, not *refused* — the row that tests the guard | FR-006 |
| `test_no_refusal_is_asserted_with_administrator_authority` | Enumeration may use an administrator; assertion may not | FR-004 |
| `test_every_existing_record_is_covered` | Nothing exists in the jurisdictions that no bounding path covers | FR-011, FR-014 |
| `test_every_enumerable_surface_is_named_or_excluded` | The named half is checked against what the control plane lists | FR-012 |
| `test_the_named_half_cannot_shrink_silently` | The five underivable bounds cannot be removed without a red row | FR-012 |
| `test_a_permitted_write_is_undone` | A write that succeeded is removed — and the row **says whether the removal worked** | FR-007, FR-008 |
| `test_nothing_here_widens_authority` | No module in this feature writes a policy or grants a capability | FR-018 |
| `test_ordinary_writes_are_not_in_scope` | A run's own secret space is untouched by this gate | FR-009 |
| `test_the_contract_states_what_this_gate_does_not_assert` | This file still records the limits the rows depend on | FR-022 |

**Fourteen paths, twelve rows.** The count of paths moves with the deployment — seven derived
from a run's read grants, seven named — and that is the intent: adding a bounding record to a
jurisdiction extends the check without anyone editing this file.


---

## What these rows do NOT assert

Stated as prominently as what they do, per ADR-0047.

- **Not that the bounding records are correct.** A ceiling granting too much, written through
  the reviewed configuration path, is invisible here. This asserts a *run* cannot change it,
  not that it is right (FR-022).
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
exceeded. FR-014 makes it a failure instead. 017 found the identical hole in its own coverage
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

**The set has a derived half and a named half, and the named half is the important one.**
A run's limits are stated twice: as a record the platform consults, and as the grant the
control plane enforces. Rewriting the grant moves the bound without touching any record — and
a run holds no read access to the grant, so nothing derived from its grants can reach it.

*Analysis pass 3 found this, after two passes had built schemes anchored on what a run can
see.* The blind spot contained the ceiling policy itself: the single most direct way a run
could widen its own authority, and the thing this feature is named after. All three named
bounds refuse today — probed 2026-07-31 — so the platform was sound throughout and the gate's
**claim** was not.

**Both halves have a completeness check, and that is the point.** The derived half is
compared against what exists in its jurisdictions; the named half against the control plane's
own enumeration of auth methods, mounts and grants. Neither rests on someone maintaining a
list — a set with one mechanism *is* a list, and a list omits in silence.

*Analysis pass 4 found the named half incomplete on the day it was written*, missing the
trusted-key configuration: write that and the control plane believes identities somebody else
mints, without any record in any jurisdiction changing.

**What the named half's check actually covers, stated precisely.** The control plane
enumerates four kinds: its mounts, its auth methods, the roles those methods issue, and the
grants it holds. Every member of those four must be named or excluded. It does **not**
enumerate "surfaces where a write would change what a run may do" — that is a judgement, and
no enumeration answers it.

**What survives**: a surface that bounds a run and is not a member of those four kinds. It is
in the named half only because somebody judged it belonged, and a new one of that shape needs
somebody to notice. Recorded here as a limit rather than left implied, because an earlier
draft of this check was phrased to sound total and would have been read that way — which is
what the four analysis passes before this one were each, in different forms, about. The named list is the part that cannot be derived and therefore
cannot self-extend; adding a bounding surface of that kind requires someone to add it here,
and T003d exists so that removing one is at least deliberate.

---

## SC-007: did anything stop running?

Per-directory `pytest --collect-only -q`, 2026-07-31. `tests/conformance/authority/` did not
exist on `main`; every other test file in the tree is byte-identical to `main` (`git diff
--stat main...HEAD -- tests/` touches three files, two of them new), so these counts **are**
the baseline for the pre-existing directories rather than a comparison against one.

| Directory | On `main` | With 018 |
| --- | --- | --- |
| `adapter/` | 12 | 12 |
| `api/` | 46 | 46 |
| `authority/` | — | **12** |
| `deployment/` | 22 | 22 |
| `durability/` | 48 | 48 |
| `evidence/` | 17 | 17 |
| `identity/` | 28 | 28 |
| `mcp/` | 56 | 56 |
| `packs/` | 30 | 30 |
| `portal/` | 8 | 8 |

Nothing stopped running. The total rises by exactly the rows this feature adds, which is the
only comparison that means anything — a feature that adds rows will always raise the total,
and a directory that quietly lost one would be invisible in that number.

---

## The one-time demonstration

Performed by hand on **2026-07-31** against a local enclave. Not a fixture, not in a lane
(FR-017): a fixture killed between grant and revoke leaves a real control plane permissive
with nobody watching, and a window that is small is not one that is closed.

**1. The original captured first, so the restore could be exact** rather than reconstructed:

```
vault policy read harness-authority-read > original-policy.hcl    # 59 lines, sha256 a6735092c378ab54
```

**2. The grant** — appended to `harness-authority-read`, the write capability the policy's own
comment says must never appear:

```hcl
path "harness-authority/data/harness-ceilings/*" {
  capabilities = ["create", "update"]
}
```

**3. The rows went red.** Two of eleven, and the output is the whole point:

```
E   AssertionError:   harness-authority/data/harness-ceilings/probe-018: permitted — HTTP 200 — the write took effect
E   AssertionError: a run WROTE a record bounding it — the platform's central claim is false.
E       harness-authority/data/harness-ceilings/probe-018: removal COULD NOT REMOVE: HTTP 403
E     	* permission denied
E
E     AND THE RECORDS ARE STILL THERE. A run granted create is not granted delete, so this
E     check created something it cannot remove:
E       harness-authority/data/harness-ceilings/probe-018
FAILED ...::test_a_run_cannot_write_any_bounding_record
FAILED ...::test_a_permitted_write_is_undone
2 failed, 10 passed
```

**The second failure is the one worth reading.** `create` does not imply `delete`, so the
check wrote a record it had no authority to remove. An earlier version of the row called the
removal and discarded its answer — which is how the first run of this demonstration left a
`probe-018` record sitting on a real control plane with nothing reporting it. That is fixed,
and the fix is visible above: the row now names the leftover rather than passing over it.

**4. The revocation, and the verification that it took** (FR-019) — an assertion that it was
revoked is exactly the kind of claim this feature exists to replace:

```
vault policy write harness-authority-read original-policy.hcl
restored byte-identical: YES          # cmp against the captured original
capability present after revoke: 0    # grep -c 'create'
12 passed                             # the rows, green again
```

**5. What the demonstration created was removed.** `harness-ceilings/probe-018` deleted with
operator authority; `vault kv list` then shows the four real definitions —
`applier-agent`, `demo-agent`, `planner-agent`, `vault-agent` — and nothing else.

---

## Two opposite meanings, one colour

**If a run's read grant were removed, every row here would fail** — correctly, because the
refusal could no longer be attributed. At a glance that is indistinguishable from isolation
having broken, and the two call for opposite responses: one is a configuration change to
undo, the other is an emergency.

The rows are built so the message tells them apart. A failure reporting
`could not attribute` means the authority can no longer see the path — the read grant went
away. A failure reporting `a run WROTE a record bounding it` means what it says. `test_a_typo_in_a_path_does_not_pass`
exists to keep the first from ever being reported as the second.
