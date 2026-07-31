# Conformance contract: 017 deployment lane

What these rows assert, what they refuse to assert, and who runs them.

---

## Who runs these rows

**Every row here is executed by an automated check** — `infra/bin/deployment-conformance`,
which is the final line of `make conformance` and therefore runs in the enclave lane without
the lane needing its own step. **No named human runner is owed** (constitution v1.1.0,
Quality Gates).

Recorded explicitly because "no runner named" and "no runner needed" look identical in a
table, and the first is a defect while the second is a property.

### Two criteria are verified once, not by a gate

**SC-006** — a contributor reaches the same verdict locally as the automated run. A Linux
runner has no macOS half to compare against, so nothing automated can re-check this. Verified
at implementation on both substrates and recorded here.

**SC-008** — repeated runs against an unchanged tree agree. Checked by
`infra/bin/deployment-conformance --repeat`, run at implementation. It stands the surfaces up
**once** and repeats the assertions: SC-008 is about the gate's determinism, and re-deploying
each pass would measure the scheduler instead while costing minutes per iteration. **Bring-up
determinism is therefore not covered** — a scheduler that placed a surface unreliably would
show up as a flaky gate, and the reading of that would be wrong. Running the repeat on every
invocation would double the lane for a property that changes only when the gate does.

**Neither is a row, and neither is silently unverified.** Re-verify both when the gate's
reach mechanism or its waits change — those are the two things that would break them. The
distinction matters because "every row is automated" is true and would otherwise be read as
"every criterion is enforced continuously", which is not.

**Why SC-008 is not a row**: a row inside `tests/conformance/deployment/` that ran the gate
would be inside the set the runner invokes, and would recurse without bound. The check
belongs one level out, in the thing that runs the rows. Found by analysis pass 2, against a
design pass 1 had just added.

---

## The rows

| Row | Asserts | Requirement | Story |
| --- | --- | --- | --- |
| `test_every_declared_process_is_asserted` | Declared processes and asserted processes are the same set — **in both directions** | FR-005 | US3 |
| `test_an_unenrolled_definition_fails` | A job definition that is neither declared nor excluded **fails the gate** | FR-005a | US3 |
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

**Adding a job definition fails the gate until someone declares or excludes it.** That is
deliberate, and it is the correction analysis pass 1 made: the first design let a process
become a subject by opting in, so a definition added without a declaration was invisible and
the gate could not fail for a process it never knew about. The friction now lands on the
exact action that has been silently losing coverage. It will read as a false positive the
first time it happens, which is why it is written down here — whoever hits it should be able
to tell the difference in one reading rather than three.

**A definition present in the tree but never deployed reads as uncovered, not absent.** Also
the correct failure — a surface nobody deployed is not a surface that works — and the
resolution is the same: declare it, or exclude it with a reason.

**These rows are enumerated by the runner script, not by a pytest line in
`make conformance`.** Analysis pass 3 found that a pytest line runs before the surfaces are
stood up, so rows there would assert against an API and a portal that do not exist and fail
on every invocation. The 010/014 lesson is "named by a lane that **will run it**", and the
runner is that lane; a row asserts the runner names this directory, so the wiring cannot be
lost the way 010's was.

**The gate cleans up after a pass, not after a failure** (FR-007a). A passing run stops what
it started, so spare capacity returns to what it was. A **failing** run leaves them standing
and says so — the allocation is what someone needs to diagnose the failure, and a failing gate
blocks the merge anyway, so nothing recurring depends on that capacity yet. Because of that,
the *next* invocation reclaims leftovers **early**, before the conformance batch job is
submitted: the gate runs last and cannot do it in time. A stop that itself fails, fails the
gate; swallowed, it would return the surfaces to persisting and report green from the
mechanism built to prevent that.

**A contributor's own processes are left alone, and that is asserted rather than promised.**
The gate reuses anything already running and never restarts it — clause 1 of FR-007a, checked
by `test_the_runner_leaves_no_footprint` alongside the teardown directions, because an
implementation that quietly restarted them would satisfy every other clause.

**Ownership is marked in the deployment record, not held in memory.** Anything the gate starts
carries a `harness_started_by` value; stopping — whether the automatic reclamation or
`make deployment-down` — acts only on processes carrying it. This is what lets clause 1 hold
*between* invocations rather than only within one: a later run has no memory of what an
earlier one started, and without the mark reclamation could only stop everything (taking a
contributor's portal with it) or stop nothing (leaving the starvation it exists to prevent).
One implementation does the stopping, called from both places, because two copies of that
decision would drift and the wrong copy decides whether someone's work survives.

**The gate stops only the surfaces it started.** If a developer brought the portal up
themselves to use it, the gate reuses it and leaves it running — so its reservations persist
and can still crowd the conformance batch job on a later run. That is the developer's own
choice and `portal-up` already warns about it; what the gate guarantees is that *it* adds
nothing durable. Recorded because "the gate leaves no footprint" and "the enclave has spare
capacity" are different claims and only the first is made.

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
