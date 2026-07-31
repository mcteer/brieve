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
| `harness_surface` | Marks this definition as in scope. Its presence *is* the declaration. | Absent → not a subject. `postgres` and `collector-postgres` are vendor images with no assembly of ours and carry no marker. |
| `harness_shape` | `served` or `dispatched`. | Must be one of the two. An unrecognised value fails the gate rather than defaulting — a typo must not silently drop a process from coverage. |
| `harness_covered_by` | Where the assertion for this process lives. | Must name something the gate can find. A declared process with no assertion fails the gate (FR-005). |

**Why the third field exists.** Two processes are already covered by rows that live
elsewhere — the dispatched entrypoint by 014's durability rows, the mcp service by 015's
shipping row (research R1, R2). Without a way to say *"covered, over there"*, the gate would
either duplicate them or silently exempt them. Naming the location makes the coverage a
claim someone can check rather than a gap nobody sees.

**Validation rule that carries the guarantee**: the set of declared processes and the set of
processes the gate has an assertion for MUST be equal. An inequality in **either** direction
fails:

- declared but unasserted → the gap this feature closes, reopened;
- asserted but undeclared → an assertion against something the deployment no longer runs,
  which is a row that will pass forever while testing nothing.

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
not_declared   ──▶  not a subject          (vendor image, no assembly of ours)
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
