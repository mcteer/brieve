# Contract: MCP conformance lane

**Feature**: `specs/009-mcp-surface`
**Status**: **In force** (all fifteen rows, as of 009's merge)
**Depends on**: Constitution Quality Gates (v1.1.0, amended by this feature); ADR-0033; ADR-0047; ADR-0049

## The row this feature amends, then satisfies

**Surface parity.** Owed since ADR-0033 and deferred through 008 for a good reason.

It is **not simply claimed here**, and the distinction survived an analyze pass rather than
the first draft. The constitutional row reads *"surface parity across all four transports"*,
and there are two — so claiming it would assert something untrue, which is the passing stub
ADR-0047 forbids, in the feature whose spec makes a point of refusing stubs.

The row is **amended to bind incrementally**: parity across every pair of implemented
transports. Better than claiming and better than deferring again, because the gate then
binds at two, at three, and at four, instead of catching nothing until the last transport
lands — which is well after divergence would have started.

## Rows in force

| Row | Asserts | Spec | Enclave | Held by |
| --- | --- | --- | --- | --- |
| **Surface parity — verdicts** | Every operation in the recorded set yields the same verdict on both transports, satisfying the **amended** row for the API/MCP pair | FR-003, FR-004, SC-001 | **yes** | `mcp/test_surface_parity.py` |
| **Surface parity — audit** | Same event types, order, subject, and decision fields; transport a field, not a structural difference | FR-003a, SC-002 | **yes** | `mcp/test_surface_parity.py` |
| **Surface parity — coverage** | An operation on one transport and not the other is detected, in either direction | FR-005, SC-003 | no | `mcp/test_surface_parity.py` |
| MCP acts as the caller | Every MCP-originated operation names the calling user as subject; zero name the service | FR-002a, SC-002a | **yes** | `mcp/test_surface_parity.py` |
| Unknown health is unhealthy | An unchecked or stale dependency refuses rather than being assumed reachable | FR-006 | no | `component/test_unknown_health_refuses.py` |
| Refusal precedes execution | A call against a known-down dependency is denied before execution and writes no intent record | FR-007, SC-004 | **yes** | `mcp/test_dependency_refusal.py` |
| Refusal placement | The gate runs **inside** the hook pipeline. Break fixture moves it to a pre-flight and asserts detection | FR-009 | no | `mcp/test_refusal_placement.py` |
| Denials stay distinct | Policy and availability denials differ in the trail, and only availability is model-visible | FR-008, SC-005 | no | `mcp/test_denial_classes.py` |
| Suspension names its dependency | A run blocked on an unreachable product suspends naming it, and no container remains | FR-010/011, SC-006 | **yes** | `mcp/test_suspend_and_sweep.py` |
| Sweep resumes on recovery | A new allocation with a new identity; zero replay a pre-suspension credential | FR-012, SC-007 | **yes** | `mcp/test_suspend_and_sweep.py`, `mcp/test_sweep_fencing.py` |
| Suspension respects the bound | A dependency down past the run's maximum duration stops the run with the reason recorded | FR-013 | **yes** | `mcp/test_suspension_bounds.py` |
| Nothing waits on a human | No path notifies, prompts, or blocks on a person | FR-014, SC-008 | no | `unit/test_nothing_waits_on_a_human.py` |
| `PARKED` is gone | Zero occurrences remain | FR-015, SC-009 | no | `unit/test_parked_is_gone.py` |
| Degraded completion | An agent returns the work it could do, naming what it did not attempt | FR-016 | no | `mcp/test_degraded_completion.py` |
| Continuous verification | The running service reports tampering with no operator action, and clean on an untampered store | FR-017, SC-010 | **yes** | `mcp/test_continuous_verification.py` |

## Break fixtures worth naming

Three, because the obvious fixture proves nothing:

- **Refusal placement** — the fixture moves the gate to a pre-flight before the pipeline and
  asserts detection. A fixture that only removed the gate would test that refusal happens,
  which the behaviour row already covers. The failure this guards is a *working* optimisation.
- **Surface parity — audit** — the fixture makes one transport emit an extra event and asserts
  the comparison catches it. A fixture that broke a verdict would be caught by the verdict row.
- **Sweep** — the fixture resumes into the *same* allocation and asserts detection. Resuming
  and completing is what a correct sweep looks like from outside; only the new-identity
  assertion distinguishes it from replay.

## CI now runs these, and that is the change

`enclave.yml` runs `make conformance` for non-fork pull requests. **This is the first feature
whose enclave rows have an automated runner.**

The constitution requires a blocking row with no automated runner to name who runs it. 005
named the agent harness for seven durability rows; 008 named it again for nine more. That
naming was honest and it was still an instruction being followed rather than a control.

**What remains named**: rows on pull requests **from forks**, where the lane cannot run — it
needs a licence secret, and exposing one to fork-controlled code would trade a coverage gap
for a credential-disclosure one. Fork contributors get the fast lane; a maintainer runs the
enclave rows. That is today's situation for everyone, narrowed to a much smaller set.

`specs/005-durable-execution/contracts/conformance-durability.md` and
`specs/008-northbound-api/contracts/conformance-api.md` were both updated to say so
(FR-022). A contract still claiming no automated runner exists would be wrong in the
direction that makes people trust the gate less than they should.

**One thing the lane does not give you**, recorded because it reads like coverage and is
not: a *skipped* job and a *passing* job are both green in the checks list. On a fork pull
request the lane skips, and the difference between "these rows passed" and "these rows were
never run" is one line of a condition that nobody looks at. `AGENTS.md` says to check that
it ran rather than that it exists.

## Dependency on something outside the code

The lane needs the Vault Enterprise licence in repository secrets. **It cannot be verified
without it**, and that provisioning is the maintainer's.
