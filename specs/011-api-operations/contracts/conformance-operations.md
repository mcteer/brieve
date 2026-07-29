# Contract: operations conformance lane

**Feature**: `specs/011-api-operations`
**Status**: **In force** (as of 011's merge)
**Depends on**: Constitution Quality Gates (v1.2.0); ADR-0033; ADR-0035; ADR-0047; ADR-0049

## The row that grows rather than the row that is added

The parity row already exists and already compares `operation_pairs()` against the
snapshot. This feature's central conformance claim is that the comparison now covers ten
operations instead of four (FR-019, SC-010) — the same row, a larger set, and a failure on
any asymmetry **in either direction**, which matters because MCP is where a "just this one
helper" is cheapest to add.

## Rows

| Row | Asserts | Spec | Enclave |
| --- | --- | --- | --- |
| Parity over the grown catalogue | Ten operations, identical on both transports; the snapshot is the set compared | FR-015, FR-019, SC-010 | no |
| Collect is a read | Polling a pending change N times advances nothing; the disposition changes only when an approver acts | FR-002, SC-001 | **yes** |
| Collect is tenant-scoped | Another tenant's accessor answers as not-found; the trail records `outside_tenant` while the caller sees `no_such_record` | FR-004, FR-020 | **yes** |
| Pending is an answer | A change whose approvers never act reads as pending indefinitely, never as failure | US1 edge | **yes** |
| List is mine and bounded | Three runs by A, one by B → A lists exactly three; pages bound; cursor stateless | FR-003, FR-005, SC-002 | **yes** |
| Withholding is silent | No count, total, or pagination artefact discloses that anything was withheld | FR-004, SC-003 | **yes** |
| The index and the trail agree | A dispatched run appears in both the run index and the audit trail — divergence is loud | plan, post-design IX | **yes** |
| Three-way result disposition | Not-finished / result / ended-without distinguishable in all cases; never the raw checkpoint payload | FR-006, FR-007, SC-004, SC-005 | **yes** |
| Stop is terminal and attributable | Terminal state, `stopped_by:<subject>` in the trail, distinguishable from a bound | FR-008, FR-012, SC-006 | **yes** |
| Stop leaves no open intent | The in-flight step completes and brackets; zero intents open after a stop | FR-008a, SC-006 | **yes** |
| The sweeper ignores stopped runs | A stopped run suspended-on-nothing is never resumed — asserted against 009's machinery, not rebuilt | FR-009, SC-006 | **yes** |
| A routine checkpoint cannot resurrect a stop | Stop a run mid-flight, let it checkpoint, assert it is still stopped. Held by `save`'s terminal-once guard — the shipped upsert was last-write-wins, and this row is what catches the guard simplifying away | FR-008, FR-009 | **yes** |
| Only the starter stops | Another subject's stop refuses; the trail records `not_permitted` | FR-010, SC-007 | **yes** |
| Stopping twice is idempotent | A second stop reports the existing state | FR-011 | no |
| Enumeration shows and marks | Both subjects see the same definitions with different `may_start`; zero cross-tenant entries | FR-013, FR-013a, SC-008 | **yes** |
| No jurisdiction leak | Zero responses contain `ceiling_policies`, paths, or policy names | FR-014, SC-009 | **yes** |
| Every operation audited | Each new operation appears in the trail attributed to the authenticated human | FR-017, SC-011 | **yes** |

## Break fixtures worth naming

- **A collect that authorizes.** The plausible defect: implementing collect against
  Vault's *request* endpoint family and picking the wrong one. The fixture calls collect
  as the sole "approver" N times and asserts the change stays pending — a collect that
  counts as an approval fails loudly here and nowhere else.
- **A cursor that carries the total.** Keyset pagination implemented with `OFFSET/COUNT`
  reads identically in the happy path; the fixture inspects the cursor for anything
  monotonic with the withheld count.
- **A save that un-terminals.** The original upsert: `SET run_state = EXCLUDED.run_state`,
  unconditional. It reads as obviously correct, passed every 005 row for three features,
  and erases a stop the next time the running allocation checkpoints. The fixture stops a
  run, forces a routine checkpoint, and asserts the terminal state survived — because the
  COALESCE guard is one simplification away from the defect at all times.

  **Run, and it caught the guard's own blind spot.** Applied for real at T041, the break
  was survived by every component row: they build the in-memory provider, and the guard is
  implemented twice. It also erased the *whole* outcome rather than only the state — a
  stopped run came back reading as one that never ended, which is worse than the described
  defect. The row that catches it is
  `tests/conformance/durability/test_rows.py::test_a_routine_checkpoint_cannot_un_terminal_a_stopped_run`,
  in the provider-parameterised lane, which is the only thing here that runs a row twice.
  A guard implemented once per provider needs a row that runs once per provider.
- **A result endpoint that returns the checkpoint payload.** Passes every disposition row
  — the result *is* in there — and makes resume state a compatibility surface. The fixture
  asserts resume-internal keys are absent from the response.

## These were run, not described (T041)

Every fixture above was applied to the tree, the row watched to fail, and the change
reverted. Three were caught by the lane that owns them. The fourth was not, and finding
that out is the whole reason the gate says *run* rather than *record*: a row nobody has
seen fail is a row nobody knows works, and the one that did not fail was the one guarding
the defect this feature was most likely to reintroduce.

## The fixture prerequisite, again

The stop rows need a run that is **still running** when the stop lands. The existing
fixture definitions complete immediately — a stop row against them passes whether the stop
works or not, which is 010's T009 finding wearing this feature's clothes. A deliberately
multi-step fixture precedes every stop row.

## Who runs these

| Where the change comes from | What covers these rows |
| --- | --- |
| Same-repo branch or pull request | The enclave lane. A required check |
| Fork pull request | **The agent harness in the IDE**, per `AGENTS.md` |
| The lane could not run | **The agent harness.** A lane that did not run is not a lane that passed |

**No new conformance directory.** 010 found its rows invisible to two lanes that each
enumerate directories by name. This feature's in-allocation rows extend
`tests/conformance/identity/`'s existing wiring and its host rows live in
`tests/conformance/api/` — both already named in both runners. The cheap lesson from the
expensive one.

## A limit worth naming before someone assumes it closed (FR-013a)

**The registry is one per deployment and carries no tenant of its own.** So "definitions
are never disclosed across tenants" holds *structurally* today — there is one registry, and
every subject of that deployment sees the same set. Nothing filters, because nothing needs
to.

A multi-tenant deployment sharing one registry would disclose definitions across tenants,
and the enumeration code would look correct while doing it. Recorded here rather than left
implicit, because this is exactly the kind of gap that reads as closed until someone
deploys the topology that opens it — and the row asserting cross-tenant absence would keep
passing, since it tests the deployment it runs in.

The fix, when a deployment needs it, is a tenant on the registration rather than a filter
in this surface: a filter would be the platform deciding what a registry means, which is
the coupling ADR-0050 kept disjoint.

## What this lane still cannot prove

- **That anything renders these operations well.** The portal is the consumer and its own
  feature; these rows prove the catalogue, not the experience.
- **Approval flows beyond one approver.** The enclave's Control Groups quorum is minimal;
  multi-approver choreography is exercised to the depth 007 established and no further.
- **Load-shaped pagination.** Pages are proven bounded and stateless, not proven pleasant
  at ten thousand runs.
