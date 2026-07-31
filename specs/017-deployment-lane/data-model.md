# Phase 1 — Data model: 017 deployment lane

This feature persists nothing. What follows is the shape of what the gate *reads* and what
it *decides*, which is where its correctness lives.

---

## DeclaredProcess

A harness-owned process the deployment runs, as declared by its own job definition. The
gate's subject.

**Source**: a `meta` block in `infra/jobs/*.nomad.hcl`. Declared where the process is added,
because that is the only place someone adding one is certainly looking (research R6).

| Field | Meaning | Validation |
| --- | --- | --- |
| `harness_surface` | Marks this definition as in scope. Its presence *is* the declaration. | Absent → **the definition must appear on the exclusion list, or the gate fails.** Absence is never silently "not a subject" — see below. |
| `harness_shape` | `served` or `dispatched`. | Must be one of the two. An unrecognised value fails the gate rather than defaulting — a typo must not silently drop a process from coverage. |
| `harness_covered_by` | Where the assertion for this process lives. | Must name something the gate can find. A declared process with no assertion fails the gate (FR-005). |

**Why the third field exists.** Two processes are already covered by rows that live
elsewhere — the dispatched entrypoint by 014's durability rows, the mcp service by 015's
shipping row (research R1, R2). Without a way to say *"covered, over there"*, the gate would
either duplicate them or silently exempt them. Naming the location makes the coverage a
claim someone can check rather than a gap nobody sees.

---

## ExcludedProcess

A job definition deliberately outside the gate's subjects, **and the reason**.

**Source**: an explicit list in `tests/conformance/deployment/surfaces.py`, checked against
the filesystem on every run so a stale entry fails rather than hides.

| Entry | Reason |
| --- | --- |
| `postgres`, `collector-postgres` | Vendor images. No assembly of ours to reach. |
| `conformance` | The gate's own runner. Asserting against it is circular. |

**Why a list here is acceptable when one was rejected as the subject list.** A stale
*subject* list silently omits a process — 010 lost a feature's rows to exactly that. A stale
*exclusion* list names something the filesystem does not have, which fails on the next run.
The failure modes are opposite, and only one of them is silent.

---

## The validation rule that carries the guarantee

**Three sets, and two equalities.** Both directions of both, because each inequality is a
different way the gate lies.

```
  definitions on disk  ==  declared ∪ excluded
  declared             ==  asserted
```

| Inequality | What it means | Verdict |
| --- | --- | --- |
| a definition in neither set | **a process nobody enrolled** — the fail-open hole | FAIL |
| excluded but not on disk | a stale exclusion, hiding nothing but claiming to | FAIL |
| declared but unasserted | the gap this feature closes, reopened | FAIL |
| asserted but undeclared | a row that passes forever while testing nothing | FAIL |

The first row is the one analysis pass 1 added, and it is the load-bearing one. Without it,
coverage is something a process opts into — and **the process nobody remembered to enrol is
exactly the one nobody remembered to cover.** A coverage mechanism that cannot see an
unenrolled process reproduces this feature's own subject matter one level up.

---

## ReachAssertion

One statement about one process, evaluated inside the enclave.

| Field | Meaning |
| --- | --- |
| `process` | Which `DeclaredProcess`. |
| `wait` | How long this process may take to reach a working state. Per process, never per gate (clarified 2026-07-31). |
| `evidence` | What the gate observed — a status, a reason code, a header. Reported on failure so the verdict is attributable. |

**States**, and the distinctions that matter:

```
on disk, undeclared, unexcluded ──▶ FAIL   nobody enrolled it, and nobody said why not
on disk, excluded              ──▶ not a subject (with a recorded reason)
declared
  ├─▶ never_started      FAIL   nothing was placed
  ├─▶ restarting         FAIL   placed, and failing repeatedly (FR-006)
  ├─▶ running            ────┐  NOT a pass — a process that assembled nothing is also running
  │                          │
  │                          ▼
  ├─▶ answered_generically  FAIL   something replied; nothing shows it was this surface
  └─▶ answered_as_itself    PASS   a response only a completed assembly produces
```

`running → answered_generically` is the transition SC-002 exists for, and the one a naive
implementation collapses into a pass. A liveness probe stops at `running`.

---

## Evidence of assembly, per process

What each surface must produce for `answered_as_itself`, and why it cannot be faked by a
process that read nothing.

| Process | Assertion | Why it entails a completed assembly |
| --- | --- | --- |
| **api** | Unauthenticated request → `401` carrying the verifier's own reason code | `build()` migrates three stores under the workload's attested identity **before** uvicorn binds, so answering at all entails reaching Vault and Postgres. The reason code additionally requires that a verifier was constructed and passed in — the exact wiring whose absence made the surface refuse everyone (PR #78). |
| **portal** | Unauthenticated request → redirect whose `Location` carries the **configured** issuer and a PKCE challenge | A process holding defaults would emit a different issuer. The challenge proves the OIDC client was constructed rather than stubbed. |
| **mcp** | *Covered elsewhere* — 015's shipping row waits for the running service to notice an entry it did not write | Requires boot, a workload credential, and a completed pass. Strictly stronger than a reach assertion. |
| **agent-run** | *Covered elsewhere* — 014's durability rows dispatch real allocations and assert completion | Requires the dispatched assembly to obtain its own identity, resolve authority, and write evidence. |

**The rejected shortcut, recorded because it is the tempting one**: asserting a `200` from a
health endpoint. It would have passed throughout the entire period the API could not start,
because a process that exits and one that is slow are indistinguishable to a checker that
retries — and FR-014 forbids the retry that would paper over it anyway.

---

## What this model deliberately does not represent

- **Correctness of any collaborator.** A store pointed at the wrong database still migrates,
  still answers, and still passes. This model distinguishes *wired to nothing* from *wired*;
  it says nothing about *wired correctly*. The spec's Assumptions say so and the conformance
  contract must repeat it.
- **Ordering between processes.** Each is asserted independently. A dependency between two
  surfaces would be a deployment concern, and none exists today.
- **History.** The gate observes the current tree. Nothing is retained between runs, which
  is what keeps FR-014 (no retry) meaningful — there is no prior verdict to fall back on.
