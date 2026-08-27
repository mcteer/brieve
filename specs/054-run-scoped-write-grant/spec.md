# Feature Specification: A run's write grant names only its own workspace

**Feature Branch**: `054-run-scoped-write-grant`

**Created**: 2026-08-27

**Status**: Draft

**Input**: User description: "A run's write authority is not scoped to the run."

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R2 / R3 (authority)** — Principle IV describes authority manufactured per task; the write half currently is not. **R4 / R13 (evidence)** — the bound must be demonstrable against the live control plane, not asserted in a fixture. **R7** — the refusal is a governed, recorded outcome |
| **ADRs touched** | **ADR-0057** (amended 2026-08-27: its trigger 1 fired, and its Decision predicted this exact split — *"where narrowing is worth having is WRITE and ACT"*). **ADR-0056** (the mechanism it established — Vault is the resource server and cannot perform the exchange). **ADR-0044** (federate-or-broker: where a write bound belongs). **ADR-0025** (structural exclusion — a run may not reach what bounds another run). **ADR-0047** (a bound that cannot be shown to refuse is a passing stub) |
| **Evidence class** | attestation-relevant — the grant a run receives is what the trust fabric will answer with when asked what a run could have done |

## User Scenarios & Testing *(mandatory)*

### The measurement that produced this feature

Demonstrated 2026-08-27 against the live dev enclave, with a token carrying exactly the
policies the `agent-run` role grants and nothing more:

| Action on **another run's** measurement policy | Result |
| --- | --- |
| Read | 200 |
| Overwrite | 200 |
| Delete | 204 — the policy was gone afterwards |

`infra/modules/trust-fabric/scratch.tf` grants `sys/policies/acl/scratch-agent-*` with
`create`, `update`, `delete` and `read`, estate-wide, to every dispatched run. The names it
protects are already per-run — `scratch-agent-{run_id}-current` and `-proposed`. **The
namespace is partitioned by convention and unpartitioned by authority.**

**The reachable route is already closed and this feature must not re-close it.** `run_id`
arrived as an unverified tool-call argument; `b7c2a2f` refuses a call claiming a foreign run
id, on every tool, fail-closed. That is layer 2. This is layer 3, and 042's own comment says
why both are needed: the ACL is *"the only one that survives a platform bug."*

**Terraform cannot express the fix.** A run id does not exist at apply time — `scratch.tf`
says so itself, noting a grant naming one policy *"fails on whichever case arrives first."*

### User Story 1 - A run's write grant names its own workspace (Priority: P1)

A dispatched Build proposing a Vault policy writes and destroys its own measurement policies
and can reach no other run's, because the authority it holds does not name them.

**Why this priority**: This is the defect. Everything else here demonstrates it or handles its
failure. Principle IV describes authority manufactured per task; for the one write capability
a run carries, it currently is not.

**Independent Test**: Take a real run's authority and attempt the three actions above against
a foreign path. Before: 200, 200, 204. After: refused, and the refusal observed rather than
inferred.

**Acceptance Scenarios**:

1. **Given** a dispatched run, **When** it writes its own measurement policy, **Then** the
   write succeeds and 042's impact check is unaffected.
2. **Given** the same run, **When** it attempts any action on a policy belonging to another
   run, **Then** the control plane refuses.
3. **Given** the run ends, **When** its authority is presented again, **Then** it no longer
   grants what it granted during the run.
4. **Given** a second run in flight, **When** either writes, **Then** neither can observe or
   alter the other's measurement.

### User Story 2 - The bound is shown to refuse, not asserted (Priority: P2)

An auditor asks whether a run can reach another run's workspace, and the answer is a recorded
refusal from the live control plane rather than a reading of the Terraform.

**Why this priority**: The defect was credible because it was demonstrated. The fix is only
credible on the same terms — ADR-0047, and the shape 018 established for registry isolation:
a real attempt under a real run's authority, against the live control plane, with every
refusal observed.

**Independent Test**: The row makes the attempt. It fails if the attempt succeeds, and it
fails if the attempt cannot be made — a row that cannot reach the path proves nothing.

**Acceptance Scenarios**:

1. **Given** the live control plane, **When** a run-shaped authority attempts a foreign write,
   **Then** the refusal is observed and recorded.
2. **Given** the same row, **When** the narrowing is removed, **Then** the row fails — a
   safety case that cannot lose has not been tested.
3. **Given** a path the authority *should* reach, **When** the row attempts it, **Then** it
   succeeds — so a refusal cannot be produced by an authority that reaches nothing.

### User Story 3 - A failure to manufacture stops the run (Priority: P3)

A Build that cannot be given a scoped grant stops and says so, rather than proceeding with a
wider one or with none.

**Why this priority**: Fail-closed is Principle III, and the honest consequence must be stated
rather than discovered: a Build proposing a Vault policy **cannot measure its impact**, so it
stops. That is correct and it is a real product outcome.

**Independent Test**: Make manufacture fail. The run stops with a distinct recorded reason;
no measurement is attempted; no wider authority is substituted.

**Acceptance Scenarios**:

1. **Given** manufacture fails, **When** the run reaches the impact check, **Then** it stops
   with a distinct reason and nothing is written.
2. **Given** manufacture fails, **When** anything looks for a fallback, **Then** there is
   none — the estate-wide grant is not retained as one.
3. **Given** the run stops, **When** a person reads the record, **Then** it says the
   measurement did not happen, distinguishable from a measurement that found no change.

### Edge Cases

- **The grant expires mid-measurement.** A scoped credential has a lifetime; a Build can be
  slower. The measurement must fail cleanly rather than half-write.
- **A run resumes.** Resumption re-observes rather than replaying; the resumed run needs
  authority for the same workspace, and whether that is the same grant or a fresh one is a
  design point, not an assumption.
- **The sweep still needs breadth.** `sweep_scratch_policies` finds orphans by listing the
  namespace, which is exactly what a run must not do. The service role holds that grant, and
  narrowing the run's must not narrow the sweeper's.
- **Two runs, one agent definition.** Entity-scoped mechanisms bind per definition, not per
  run. Two concurrent runs of the same definition are the case that breaks a naive
  identity-templated policy.
- **A run with no write need at all.** Most runs never call the impact check. Whether they
  receive a scoped grant they never use, or none, is a real choice.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A dispatched run's write authority MUST name only workspaces belonging to that
  run. Reaching another run's MUST be refused by the control plane, not only by the pipeline.
- **FR-002**: The narrowing MUST be enforced where it survives a platform bug — in the trust
  fabric's own answer — because the pipeline guard already exists and is a different claim.
- **FR-003**: The refusal MUST be demonstrable against the live control plane by a real
  attempt under a real run's authority, in the shape 018 established.
- **FR-004**: A row MUST fail if the narrowing is removed, and a row MUST show the authority
  reaching what it legitimately should — a refusal from an authority that reaches nothing
  proves nothing.
- **FR-005**: When scoped authority cannot be manufactured, the run MUST stop with a distinct
  recorded reason. No wider authority may be substituted and no measurement may proceed.
- **FR-006**: Read scope MUST NOT be narrowed. ADR-0057's reasoning is untouched and this
  feature may not reverse it.
- **FR-007**: The existing pipeline guard (`run_id_forged`) MUST remain. This feature adds a
  layer; it does not replace one.
- **FR-008**: The orphan sweep MUST keep the breadth it needs. Narrowing a run's authority may
  not narrow the service role's.
- **FR-009**: The cheapest sufficient mechanism MUST be established by evidence before a
  larger one is built, and the rejected alternatives recorded with what ruled them out.
- **FR-010**: The per-tool `paths` declaration already in the pack manifest MUST be the input
  the narrowing derives from, or the spec MUST record why it cannot be.
- **FR-011**: What a run's authority actually granted MUST remain answerable after the run, so
  an auditor can say what it could have done.

### Key Entities

- **Run workspace**: the measurement policies belonging to one run. Named per run today and
  bounded per estate; this feature makes the bound match the name.
- **Scoped write grant**: authority naming one run's workspace, manufactured at run time
  because no apply-time artifact can name it.
- **Tool path declaration**: the per-tool `paths` already in pack manifests. It arrived with
  016 for exactly this purpose and has been read by nothing since — `risk_class` sat unread
  for two features before 013 gave it meaning.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A run-shaped authority attempting any action on another run's workspace is
  refused by the control plane — 100% of attempted actions, measured live, where the same
  attempts returned 200/200/204 on 2026-08-27.
- **SC-002**: The same authority still performs its own run's measurement, so 042's impact
  check is unchanged for every corpus case that exercises it.
- **SC-003**: Removing the narrowing makes at least one row fail.
- **SC-004**: Every failure to manufacture stops the run with a distinct reason; none proceeds
  unmeasured and none is reported as another failure.
- **SC-005**: Read scope is unchanged — no path a run could read before is refused after.
- **SC-006**: The mechanism chosen is the cheapest that satisfies SC-001, with the rejected
  alternatives recorded and the evidence that ruled each out.

## Assumptions

- **The pipeline guard stays and is assumed working.** `b7c2a2f` closed the model-driven
  route. This feature assumes it holds and adds the layer beneath it.
- **The parked substrate is re-derived, never merged.** `archive/016-task-scoped-authority`
  is ~36,000 lines behind main across 251 files. Its research survives in
  `specs/016-task-scoped-authority/research.md` and is treated as findings to re-verify, not
  as code to restore.
- **The knowledge that cost the most is carried forward**: `jti` is mandatory and its absence
  reports only in Vault's server log while the caller sees a bare 403; `use_jwks` defaults
  true, so static keys need it set false explicitly; the entity binds through an alias on the
  agent-registry mount carrying `external_id` and `issuer`, which the typed Terraform resource
  cannot express.
- **Only the scratch namespace is in scope.** It is the only write capability a dispatched run
  carries today.

## Out of Scope

- Narrowing read scope, in any form.
- Widening what any run may do.
- Replacing the `run_id_forged` pipeline guard.
- Merging the parked 016 branch.
- Changing what `vault_policy_impact` measures or reports.
