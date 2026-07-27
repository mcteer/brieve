# Contract: Gated paths

**Feature**: `specs/007-control-groups`
**Status**: Planned
**Depends on**: ADR-0016, ADR-0015

## Purpose

Name exactly what requires quorum and what does not. A gate whose scope is vague is one
that gets widened until it is unusable, or narrowed until it is decorative.

## Gated — changes what an agent may become

| Path class | Why |
| --- | --- |
| Ceiling policies | The outer bound on everything an agent may ever do |
| Agent definitions and registry entries | Creating authority that did not exist |
| Workload identity role bindings | What may authenticate as a definition |
| Break-glass access | By construction |
| Reactivation of a suspended agent | Restoration, which is the gated half of the asymmetry |
| The quorum policy itself | Or the control can be lowered by whoever it constrains |

## Not gated — operating within what was approved

| Operation | Why |
| --- | --- |
| Scheduling, restarting, scaling an instance | The approval already happened, at the definition |
| Registering an instance of an approved definition | Same |
| Issuing per-step credentials within a ceiling | This is the per-task authority model working |
| **Revocation** | Unilateral and immediate, deliberately |

## Invariants

1. **Gating attaches to the path, not the caller.** A gate on callers is a gate on the
   callers someone thought of; a gate on the path holds for the CLI, Terraform, the API,
   and a northbound surface that does not exist yet.
2. **Our own tooling is subject to it.** Once the policy is in force, applying a ceiling
   change from the deployment tree requires approvals like anything else. Correct, and
   slightly uncomfortable.
3. **Provisioning happens before the policy binds** (FR-016) — the only reason the
   bootstrap terminates.
4. **Revocation is never gated.** A control that makes revoking as slow as granting is one
   people route around in an incident, after which the route-around is the normal path.
5. **No gated path can pause a run.** These are authority changes; runs hold authority
   already granted.

## Related

- [quorum-policy.md](./quorum-policy.md)
- [evidence.md](./evidence.md)
