# Research: Control Groups

**Feature**: `specs/007-control-groups`
**Date**: 2026-07-26

## Decision: The gate is Vault's Control Groups, configured — not an approval engine, built

- **Decision**: Express the quorum requirement as Vault Control Group policy in the
  `trust-fabric` module. The harness never evaluates approvals; it observes outcomes.
- **Rationale**: FR-014, Principle I, Principle VII. Verified against the running enclave
  that Control Groups is licensed — `Control Groups licensed: True` — rather than trusted
  from documentation, because the whole plan collapses if it is not.
- **Why building one would be worse than duplicative**: an approval engine beside the trust
  fabric means two records of who may do what, and they will disagree eventually. ADR-0015
  designates the control-plane Vault as *the* authority record. A second one is not a
  redundancy, it is an ambiguity — and during an incident someone reads the wrong one.
- **Alternatives considered**: a harness-side approval service (above). Sentinel
  endorsement without Control Groups (Sentinel gates *policy evaluation*; Control Groups
  gate *access pending human approval* — the latter is what ADR-0016 describes). A
  ticketing-system integration (puts the authority record outside the trust boundary
  entirely, and makes the gate only as good as an integration nobody tests).

## Decision: Gate the paths, not the callers

- **Decision**: The controlled paths are those that change what an agent may become — the
  ceiling policies, the definition and registry entries, the JWT role bindings, restoration
  of revoked authority, and the quorum policy itself. Gating attaches to the *path*, so it
  holds regardless of who calls it or through what tool.
- **Break-glass is deliberately not among them.** Root regeneration requires a quorum of
  unseal-share holders and is a `sys` operation outside normal policy paths — Control Groups
  cannot intercept it, and it is already a stronger multi-party control. Its strength is set
  by the unseal threshold, not by this feature.
- **Rationale**: FR-001–FR-003. A gate on a caller is a gate on the callers you thought of.
  A gate on the path holds for the CLI, the API, Terraform, and whatever comes next —
  including a future northbound surface that does not exist yet.
- **The consequence worth knowing**: this means *our own Terraform* is subject to the gate
  once the policy is in force. That is correct and slightly uncomfortable: applying a
  ceiling change from the deployment tree will require approvals like any other change.
  Provisioning happens before the policy binds (FR-016), which is the only reason the
  bootstrap terminates.
- **Alternatives considered**: gating by identity or role (misses any path a new caller
  reaches). Gating in the harness rather than Vault (the harness is not the only writer —
  Terraform and the Vault CLI are too).

## Decision: Revocation bypasses the gate by design

- **Decision**: Revocation paths are deliberately **not** controlled. Any authorized
  identity revokes alone and immediately. Only restoration is gated.
- **Rationale**: FR-006/FR-007 and ADR-0016's asymmetry. The control is "easy to make safe,
  hard to make permissive". Symmetry would be the intuitive design and the wrong one.
- **The failure it prevents is behavioural, not technical**: if revoking is as slow as
  granting, people route around it during an incident — and the route-around becomes the
  normal path, at which point the gate protects nothing.
- **Alternatives considered**: symmetric gating (above). Revocation with post-hoc review
  (review after the fact is a report, not a control, and nobody reads it).

## Decision: The harness observes; it does not decide

- **Decision**: A small core module records authority-change events into the existing audit
  chain — request, approvals with identities, disposition — and surfaces a distinct error
  when an operation is blocked pending approval. It performs no evaluation.
- **Rationale**: Principle IX and FR-011. Vault holds the decision; the harness must be
  able to *show* it, joined to the definition it changed, without becoming a second place
  that decides.
- **Why a distinct error matters**: "blocked pending approval" is not a denial. A caller
  that treats it as one will retry forever or report failure, when the correct behaviour is
  to stop and let the approval happen. Reusing the deny path would make an in-flight
  approval indistinguishable from a refusal.
- **Alternatives considered**: mirroring Vault's approval state into Postgres (a second
  source of truth about who approved what — the thing this decision exists to avoid).
  Recording nothing and relying on Vault's audit device (Vault's log is not joined to the
  harness's correlation IDs, so an investigator would have to correlate by hand).

## Decision: Test against the real Vault; a faked quorum proves nothing

- **Decision**: Component tests run against the control-plane Vault in the enclave. There
  is no fake Control Group.
- **Rationale**: a fake that always approves proves the caller can proceed; one that never
  approves proves the caller handles denial. Neither proves the gate holds, which is the
  only claim that matters. This is the same reasoning that put the durability rows on real
  Postgres.
- **Cost, stated**: these tests need `make dev-up`, so CI cannot run them. They are
  component tests rather than conformance rows, so v1.1.0's named-runner requirement does
  not attach — that rule governs blocking rows in the Quality Gates list, and this feature
  adds none.
- **Alternatives considered**: a fake control group (above). Unit-testing the policy
  document as text (asserts the policy says what we wrote, not that Vault enforces it).

## Decision: Nothing in this feature touches a run

- **Decision**: No run-time interrupt, no approval hook productization, no pause. FR-012
  and SC-009 state it as a requirement, and `tests/unit/test_no_run_interrupt.py` asserts
  it.
- **Rationale**: ADR-0049 (Proposed) — consent to start is consent to finish. This feature's
  subject is humans authorizing, which is precisely the shape that grows a run-time
  interrupt unless something forbids it.
- **Why assert a negative**: because negative requirements are the ones that quietly stop
  being true. Nobody will notice the day a pause is added; a failing test will.
- **Alternatives considered**: productizing 004's approval hook here (that hook is the
  run-time interrupt shape ADR-0049 is removing; settling it belongs to 0049, not here).

## Decision: Quorum policy is the customer's, seeded by the tree

- **Decision**: Quorum size and approver identities are Terraform inputs with no meaningful
  default. The deployment tree may seed a starting configuration during provisioning; the
  customer's control-plane Vault administrator owns it thereafter.
- **Rationale**: FR-015/FR-016. Humans build the foundations that determine how agents may
  behave; the platform enforces what they set rather than deciding it for them. A default
  quorum would be a decision made for every customer by whoever wrote the module.
- **The bootstrap, named**: the policy gates its own changes, so it cannot create itself.
  Provisioning applies it before the bootstrap credential is revoked — the same shape as
  TLS in 006, where something outside the loop goes first.
- **Alternatives considered**: a sensible default (decides for the customer, and a quorum of
  two chosen by us is a security posture we do not know is right for them). No seeding at
  all (leaves a window where the paths are ungated and nobody notices).

## Correcting the record: two mechanisms, and root bypasses both

Established by testing against the running enclave during implementation. Both corrections
change the design rather than refining it, so they are recorded here rather than left in a
commit message.

- **The approval workflow is an ACL `control_group` stanza, not a Sentinel EGP.** The plan
  said "Sentinel endorsement policy". Testing showed an EGP produces a flat **permission
  denied** — while a policy carrying a `control_group` stanza returns a **wrapping token**,
  which *is* the pending approval request. That matters because the spec requires
  "blocked pending approval" to be distinguishable from denial (`contracts/evidence.md`),
  and Vault already makes that distinction natively. We do not have to invent it.
- **But the stanza lives in a policy, so the gate is only as complete as the set of
  policies granting those paths.** A new policy granting the same path without the stanza
  bypasses it silently. So the EGP stays as a **backstop**: path-attached, catching exactly
  that case, denying rather than queuing — the correct outcome for a path someone granted
  without a gate.
- **A root token bypasses both.** Verified: root wrote to a gated path with no approval and
  no denial. This is not a flaw to work around. It is why the production profile revokes the
  bootstrap credential — revocation is not hygiene, it is what makes the gate real. It also
  means the development enclave, which retains its root token deliberately, **cannot
  demonstrate the gate through that token**, and tests must use a non-root identity.

The generalisable lesson: this feature's premise was "configure the mechanism rather than
build one", and configuring a mechanism still requires knowing what it actually does. Two
readings of the documentation were both plausible and one was wrong; ten minutes against a
real Vault settled it.
