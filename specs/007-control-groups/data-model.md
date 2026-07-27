# Data Model: Control Groups

**Feature**: `specs/007-control-groups`
**Date**: 2026-07-26

Most of what matters here lives in Vault, not in this codebase. What follows names the
objects, says which side of the boundary each falls on, and — for the ones the harness
touches — what it may and may not do with them.

## Where each object lives

| Object | Owned by | The harness may |
| --- | --- | --- |
| Quorum policy | The customer's control-plane Vault administrator | Read it. Never write it |
| Authority change request | Vault | Observe and record |
| Approval | Vault | Observe and record |
| Authority change event | The harness | Record, joined to a correlation ID |
| Revocation | Any authorized identity, through Vault | Observe and record |

The second column is the design. A harness that could write quorum policy would be a
harness that could lower the gate constraining it.

## QuorumPolicy *(Vault-side, customer-owned)*

| Field | Rules |
| --- | --- |
| `change_class` | Which class of change this governs — ceiling, definition, registration, role binding, restoration, or the quorum policy itself. **Not break-glass**: root regeneration is gated by the unseal threshold, which this policy cannot reach |
| `required_approvals` | How many distinct identities must assent. No default: a quorum chosen by us is a security posture we do not know is right for them |
| `authorized_approvers` | Who may assent |
| `request_ttl` | How long a request may remain pending before it expires |

**Validation**: the policy gates changes to itself (FR-015). It is created during
provisioning, before the bootstrap credential is revoked (FR-016) — a control that gates
its own changes cannot create itself, and naming that bootstrap is what prevents either a
control that never exists or one with a permanent back door.

## AuthorityChangeRequest *(Vault-side)*

| Field | Rules |
| --- | --- |
| `request_id` | Opaque |
| `controlled_path` | The path being written — the gate attaches here, not to the caller |
| `requester` | The identity that proposed it |
| `approvals` | Assenting identities. **The requester's own does not count** (FR-008) |
| `expires_at` | Past this, the request is dead and the change does not happen |

**Validation**: reaching `required_approvals` is the only thing that lets the write
proceed. There is no path where a request takes effect by timeout, default, or escalation
(FR-009) — expiry means *no change*, which is the safe direction.

**Evaluated against the policy in force when it completes**, not when it was raised
(FR-018). Otherwise raising a request just ahead of a tightening slips it through under the
looser rule, and tightening becomes advisory.

## AuthorityChangeEvent *(harness-side — the evidence)*

What this feature adds to the audit chain. It is a **record of what Vault decided**, not a
second decision.

| Field | Rules |
| --- | --- |
| `correlation_id` | Joins this event to everything else an investigator walks |
| `controlled_path` | What was being changed |
| `disposition` | `requested` / `approved` / `denied` / `expired` |
| `identities` | Requester, and each approver or denier |
| `occurred_at` | |

**Validation**: holds no credential material and no policy content — an audit record of an
authority change is not a place to copy the authority itself.

**It is deliberately not a mirror of Vault's approval state.** Keeping a synchronised copy
would create a second answer to "who approved this", and during an incident someone reads
the wrong one. This records that a decision happened and what it was; Vault remains where
the decision *is*.

## Blocked-pending-approval, as an outcome

Not an entity — a distinction the error surface must preserve.

| Outcome | Meaning | Correct caller behaviour |
| --- | --- | --- |
| **Denied** | Authority refused it | Stop. Do not retry, do not route around |
| **Blocked pending approval** | Nobody has refused; humans have not answered yet | Stop, and let the approval happen |

Collapsing these would make an in-flight approval indistinguishable from a refusal: a
caller would either retry forever or report a failure that is not one. They need distinct
reason codes.

## What has no state transitions here

Deliberately: **runs**. Nothing in this data model touches `RunState`, and nothing in this
feature moves a run between states. An agent mid-run holds authority already granted
(FR-012, FR-013).

A narrowed ceiling applies to authority manufactured *after* the change. Credentials
already issued expire on their own schedule; the platform does not reach into a running
step.

## Validation summary (normative)

1. The harness never writes quorum policy.
2. A requester's own approval never counts toward quorum.
3. No change takes effect by timeout, default, or escalation; expiry means no change.
4. A request is evaluated against the policy in force at completion.
5. Revocation requires zero approvals; restoration requires quorum.
6. Every request, approval, denial, and disposition is recorded and joinable by correlation ID.
7. No object here holds credential material or policy content.
8. Nothing in this feature transitions a run between states.
