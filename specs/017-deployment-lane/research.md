# Phase 0 — Research: 017 deployment lane

Everything below was established against the repository and the running enclave, not
inferred. Two findings shrink the feature; one changes where it runs; two reuse traps this
repository has already paid for.

---

## R1 — The dispatched process is ALREADY covered. FR-013 is mostly satisfied.

**Decision**: Do not build dispatch machinery. Assert that the coverage exists, and record
what it does and does not prove.

**Finding**: `tests/conformance/durability/` dispatches **real** `agent-run` allocations
through the production `NomadDispatcher` and asserts they reach completion —
`test_dispatched_resume.py::test_row_a_killed_dispatched_run_resumes_and_completes_exactly_once`
and eight sibling rows. They run in `make conformance` via the `host_enclave` line. So the
dispatched entrypoint's assembly *is* exercised by a merge-blocking lane today.

**This contradicts the emphasis clarify put on Story 5**, and the honest reading is that
014 already closed the dispatch half of gap 0d — which is exactly why three of the five
known instances were *found* by 014. They were found by building this coverage. What
remains is that the coverage is **incidental**: it exists because durability rows happen to
need a dispatch, not because anything asserts that the dispatched process must be covered.
A future change that stopped dispatching would silently remove it.

**Rationale**: Rebuilding it would be duplication, and Principle VII forbids two ways to
run one gate. Story 5's residue is FR-005 applied to the dispatched shape — an assertion
that the coverage is present — not FR-013's machinery.

**Alternatives considered**: A dedicated "dispatch a trivial run" row. Rejected: it would
assert less than the durability rows already assert, while costing another dispatch in a
lane whose resource envelope is already the binding constraint (R4).

---

## R2 — The mcp service is covered; the API and portal are covered by nothing.

**Decision**: The new surface area is **two** processes, not four.

**Finding**, by lane:

| Process | Shape | Covered today | By what |
| --- | --- | --- | --- |
| `agent-run` | dispatched | **Yes** | 014's durability rows (R1) |
| `mcp` | served | **Yes** | `test_the_service_ships.py` — writes to the first copy and waits for the *running service* to notice, which requires it to have booted, obtained a credential as a workload, and completed a pass |
| `api` | served | **No** | nothing starts it |
| `portal` | served | **No** | nothing starts it |

`make dev-up` runs `enclave-up`, which brings up Vault, Nomad, Postgres, the mcp service
and `agent-run`. `infra/bin/portal-up` brings up the API and the portal, and **no lane
invokes it.**

**Rationale**: Recording this bounds SC-007 honestly. The feature is smaller than the spec
implies, and saying so is worth more than the appearance of a larger one.

**Alternatives considered**: Treating all four as uncovered and writing four new rows.
Rejected — it would duplicate two working gates and inflate the claim.

---

## R3 — What "answered" must mean, and why the API's own start order settles it

**Decision**: Assert that an **unauthenticated** request receives the surface's **own
refusal**, carrying its reason code. Not a health endpoint, not a socket connect.

**Finding**: `surfaces/api/service.py::build()` runs `audit_sink.migrate()`,
`run_index.migrate()` and `thread_store.migrate()` — each of which draws a dynamic
credential from Vault under the workload's attested identity and connects to Postgres —
**before** `create_app` is called and before uvicorn binds. So for the API, *answering at
all* already entails that Vault and Postgres were reached. This is why the process died
rather than serving badly when its Vault role was wrong.

The assertion therefore needs only to distinguish "this surface answered" from "something
answered":

- **API**: an unauthenticated request returns `401` with `{"detail": "absent_identity"}` —
  the verifier's own reason code, which only exists if `create_app` received a verifier.
  Verified against the running service on 2026-07-31.
- **Portal**: an unauthenticated request redirects to sign-in, and the `Location` carries
  the **configured issuer** and a PKCE challenge. That proves the portal read its
  configuration, which a process holding defaults would not have.

**Rationale**: SC-002 is the criterion a naive implementation misses. A liveness check
returns 200 from a process that read nothing; both assertions above are unproducible
without a completed assembly.

**Alternatives considered**:
- *A `/healthz` returning 200.* Rejected — it is exactly the check that would have passed
  throughout the period the API could not start.
- *A successful authenticated request.* Rejected — it needs a valid end-user token from an
  external provider inside a merge gate, which the spec's assumptions already exclude.

---

## R4 — Where the lane runs: sequential, inside the existing enclave lane

**Decision**: Extend the existing enclave lane. Stand the two surfaces up **after**
`make conformance` completes, and assert against them there.

**Finding**: The resource envelope is the binding constraint and it has already bitten.
`infra/bin/enclave-conformance` carries the scar in a comment:

> *"when the scheduler refused to place the job — which it did on every CI run of a branch
> that added one more workload"*

and `infra/bin/portal-up`'s own header records why it is separate from `make dev-up`:

> *"registering them at bring-up blocked the enclave CI lane for ten minutes on a service
> deployment, and their resource reservations left the conformance job unplaceable, so the
> merge-blocking durability rows never ran."*

Sequencing resolves this by construction. The `conformance` batch job **completes and
releases its reservation** before the surfaces are submitted, so nothing competes. FR-007
is then satisfied structurally rather than by tuning numbers.

**Rationale**: A third lane would repeat a ~12-minute enclave bring-up for two assertions.
Adding the surfaces at bring-up recreates the exact failure the separation exists to
prevent.

**Alternatives considered**:
- *A third CI lane.* Rejected on cost and on Principle VI — an additional operated
  component needs a named trigger, and "we did not want to sequence" is not one.
- *Surfaces at bring-up.* Rejected — documented to have made the merge-blocking rows
  unplaceable, which is worse than the gap being closed.

---

## R5 — The assertion runs through the scheduler, not from the shell

**Decision**: Reach each surface with `nomad alloc exec` into that surface's own
allocation.

**Finding**: Both surfaces use `network_mode = "host"`. On a Linux runner the host *is* the
runner, so a shell can reach `127.0.0.1:8081`. On Docker Desktop for macOS the "host" is
the Linux VM, and the developer's shell is **not** inside it — verified on 2026-07-31, when
`curl http://127.0.0.1:8081/runs` returned nothing while the same request from inside the
allocation returned `401 absent_identity`.

A row curling from the shell would therefore pass in CI and fail locally for a reason
having nothing to do with the tree, breaking FR-008 and Principle VII's "identical
conformance suite across substrates".

**Rationale**: `nomad alloc exec` is uniform on both, because it goes through the scheduler
rather than through the host's network namespace.

**Alternatives considered**:
- *Publish ports.* Rejected — it changes the deployment to suit the test, so the gate would
  assert against a configuration no deployment uses.
- *A substrate-conditional row.* Rejected — Principle VII permits the substrate as the only
  delta, and this would make the *assertion* differ, not the substrate.

---

## R6 — Coverage by construction, via a marker in the jobspec

**Decision**: The gate enumerates **every** job definition and fails on any that is neither
a declared subject nor an explicitly excluded one. Declaration lives in the job definition
itself.

**Corrected by analysis pass 1 (2026-07-31).** The first version of this decision had the
gate enumerate *marked* definitions only, which is fail-open: a definition added without a
marker is invisible, and the gate cannot fail for a process it never knew about. The
process nobody remembered to enrol is exactly the one nobody remembered to cover. Inverting
the default costs an exclusion list — and an exclusion list is the point, because each
entry carries a reason someone had to write down.

**Finding**: No jobspec currently carries a `meta` block, so this is purely additive. Eight
definitions exist and every one needs a verdict:

| Definition | Disposition |
| --- | --- |
| `api`, `portal` | Subjects — the two this feature adds |
| `mcp` | Subject, `harness_covered_by` naming 015's shipping row |
| `agent-run` | Subject, dispatched shape, covered by 014's durability rows |
| `postgres`, `collector-postgres` | **Excluded** — vendor images, no assembly of ours |
| `conformance` | **Excluded** — the gate's own runner; asserting against it is circular |
| `harness-probe` | **Needs a verdict.** Ours and batch-shaped; unaddressed until analysis pass 1 raised it |

Deriving the set from `type` does not work: `type = "service"` also matches the two vendor
images, and the value is supplied as a variable in five of the eight files, so static
parsing is unreliable.

**Rationale**: FR-005 says a process added to the deployment must be covered *or the gate
must fail for not knowing how*. A declaration in the job definition puts the obligation
where the process is added, which is the only place someone adding one is certainly
looking.

**Alternatives considered**:
- *A list in the test suite.* Rejected as the **subject** list — it is the thing that goes
  stale, and 010 lost a feature's rows to exactly that. Accepted as the **exclusion** list,
  which is different: it is checked against the filesystem on every run, so a stale entry
  fails rather than hides.
- *Querying the scheduler for running jobs.* Rejected — it enumerates what IS running, so a
  surface that failed to start is absent from the set and the gate passes. That inverts the
  guarantee.
- *Marker-only enumeration.* Rejected by analysis pass 1, above. Fail-open.

---

## R7 — The replay trap is already solved, and must not be re-solved differently

**Decision**: Reuse the purge-before-submit discipline for anything batch-shaped.

**Finding**: `infra/bin/enclave-conformance` purges the `conformance` job before
submitting it, and records why:

> *"A completed batch job is not re-run by `job run`: Nomad compares an identical jobspec
> against the dead job, changes nothing, and places no allocation. The script then read the
> PREVIOUS allocation's logs and exit code and reported them as this run's verdict.
> Measured: a real run places a new allocation and takes ~15s; a second run took 3s,
> reported the first run's result, and never executed a row."*

This is FR-013's requirement — a prior run's evidence must not satisfy the gate — already
diagnosed and paid for, one job over.

**Rationale**: The same trap applies to a service whose jobspec has not changed:
`nomad job run` against an identical spec places no new allocation, so the gate would
assert against a container started before the change under test. The lane must force a new
allocation or verify the running one postdates the tree.

**Alternatives considered**: Trusting `job run` to redeploy. Rejected — observed on
2026-07-31, when resubmitting the API with an unchanged jobspec did not restart it and the
old code answered.

---

## R8 — FR-014 (no retry) is affordable here, and one thing threatens it

**Decision**: Accept FR-014 as written. Name the risk rather than soften the rule.

**Finding**: The assertions are two HTTP requests against processes that are already up.
The variance is in **start-up**, not in the assertion — and start-up is bounded by
per-process waits under SC-004. The one real intermittency risk is the `uv` dependency
install each allocation performs before serving, which is cache-dependent.

**Rationale**: A generous per-process wait converts that variance into latency rather than
into failure, which is precisely why SC-004 is per-process (clarified 2026-07-31).

**Alternatives considered**: A retry budget. Rejected by FR-014, and the spec records the
cost of that choice in its Assumptions.

---

## Residual unknowns

**None blocking.** One item is deliberately left to implementation rather than resolved
here: the exact per-process wait values. They are a measurement, not a decision — take the
observed cold-start time on the CI runner and set the wait well above it. Setting them from
a guess here would put a number in the plan that the first red run disproves.
