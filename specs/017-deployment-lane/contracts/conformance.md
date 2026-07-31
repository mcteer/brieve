# Conformance contract: 017 deployment lane

What these rows assert, what they refuse to assert, and who runs them.

---

## Who runs these rows

**Every row here is executed by an automated check** — the enclave lane, extended with one
step after `make conformance`. **No named human runner is owed** (constitution v1.1.0,
Quality Gates).

Recorded explicitly because "no runner named" and "no runner needed" look identical in a
table, and the first is a defect while the second is a property.

---

## The rows

| Row | Asserts | Requirement | Story |
| --- | --- | --- | --- |
| `test_every_declared_process_is_asserted` | The set of processes declaring themselves in the deployment equals the set the gate asserts against — **in both directions** | FR-005 | US3 |
| `test_the_api_answers_as_itself` | An unauthenticated request to the running API returns its own refusal reason, not a generic rejection | FR-003, FR-009 | US1, US2 |
| `test_the_portal_read_its_configuration` | The running portal redirects to sign-in at the **configured** issuer, with a PKCE challenge | FR-003 | US1, US2 |
| `test_the_dispatched_process_is_covered` | The dispatched entrypoint is asserted somewhere, and that assertion dispatches rather than reading prior records | FR-005, FR-013 | US5 |
| *(break fixture)* | A surface whose assembly is deliberately broken fails the gate | FR-012 | US1 |

---

## What these rows do NOT assert

Stated as prominently as what they do, per ADR-0047: a gate that overstates its guarantee is
worse than one that skips, because the overstatement is believed.

- **Not that any collaborator is correct.** A store pointed at the wrong database migrates,
  answers, and passes. These rows distinguish *wired to nothing* from *wired*. Describing
  this feature as proving the deployment correct would be an overstatement.
- **Not that an authenticated request succeeds.** That needs a valid end-user token from an
  external identity provider, and a merge gate depending on a third party's availability
  trades one flaky class for another. The assertions are refusals for that reason.
- **Not that the surfaces agree with each other.** Surface parity is 009's gate and compares
  what the transports *offer*; this compares nothing across surfaces.
- **Not that a surface performs.** No latency or throughput claim is made. The per-process
  waits are generous by design (SC-004) and are not performance targets.

---

## Known limits, recorded rather than closed

**A job definition present in the tree but never deployed reads as uncovered, not absent.**
The gate enumerates from `infra/jobs/`, so adding a definition ahead of deploying it fails
the gate. This is the correct failure — a surface nobody deployed is not a surface that
works — but it will read as a false positive the first time it happens, and it is written
down here so whoever hits it can tell the difference in one reading rather than three.

**Two processes are covered by rows that live elsewhere.** The dispatched entrypoint by
014's durability rows; the mcp service by 015's shipping row. Those rows are stronger than a
reach assertion, and duplicating them would be two gates for one guarantee (Principle VII).
The declaration names where each is covered, so the coverage is checkable rather than
assumed — but a change that gutted one of those rows while leaving its name in place would
not be caught here.

**SC-007 must be answered honestly, including the parts that are unflattering.** The
assessment of the five known instances belongs in this contract when the feature lands, and
it must record any the gate would **not** have caught. On the research available now, the
expected answer is that three of five were in the dispatched path and were caught by 014
rather than by this gate — which means this feature's *own* contribution is narrower than
the gap entry implies, and the contract should say so plainly.

---

## The break fixture

FR-012 requires the gate to fail against a deliberately broken assembly, demonstrated rather
than argued. The repository has an established practice of break fixtures for exactly this.

The break must be **in the assembly**, not in the surface's behaviour: point a surface at a
credential role that does not exist, which is precisely the defect that motivated the
feature. A fixture that broke a route would prove the row can fail without proving it can
detect the failure class it exists for.

---

## Reason codes and evidence

On failure a row reports the process, its state, and what was observed — a status code, a
reason code, a `Location` header. A row that reported only "assertion failed" would leave
whoever reads it unable to tell a broken surface from a broken row, which FR-004 forbids.

The surrounding script captures and prints the scheduler's own placement output on failure.
`infra/bin/enclave-conformance` records the cost of not doing this: *"A gate that will not
say why it failed costs more than the failure"* — three rounds of diagnosis went into
guessing which resource came up short, because the output was discarded.
