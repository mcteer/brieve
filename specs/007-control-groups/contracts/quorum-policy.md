# Contract: Quorum policy

**Feature**: `specs/007-control-groups`
**Status**: Planned
**Depends on**: FR-008, FR-009, FR-015–FR-018

## Purpose

Define what the policy must express, who owns it, and the rules that hold regardless of how
it is configured.

## Ownership

**The customer's control-plane Vault administrator specifies it.** The deployment tree may
seed a starting configuration during provisioning; the platform does not decide it.

Humans build the foundations that determine how agents may behave. The platform enforces
what they set — it does not choose it for them, and a default quorum shipped by us would be
a security posture chosen for every customer by whoever wrote the module.

## Configurable

| Setting | Notes |
| --- | --- |
| Required approvals, per class of change | **No default.** Absent configuration is not a quorum of one |
| Who may approve, per class | |
| Request TTL | How long before a pending request expires |

## Invariants — true regardless of configuration

1. **A requester cannot satisfy their own quorum** (FR-008). Otherwise the requirement is
   one person with two hats.
2. **No change takes effect by timeout, default, or escalation** (FR-009). Expiry means the
   change does not happen — the safe direction.
3. **A request is evaluated against the policy in force when it completes** (FR-018), not
   when raised. Otherwise raising one just ahead of a tightening slips through under the
   looser rule.
4. **The policy gates its own changes** (FR-015).
5. **It is created before the bootstrap credential is revoked** (FR-016). A control gating
   its own changes cannot create itself; the alternatives are a control that never exists
   or one with a permanent back door.
6. **An unreachable approval mechanism blocks changes** (FR-010) — and only changes. Agent
   runs already holding authority continue. Failing closed on the wrong thing here would
   halt the platform during a Vault blip.

## Root bypasses the gate

Verified against a running Vault: a root token writes to a gated path with no approval and
no denial.

This is why the production profile revokes the bootstrap credential. Revocation is not
tidiness — **it is what makes this gate real**. A deployment that keeps a root token has an
authority gate anyone holding that token can walk around.

The development enclave retains its root token deliberately, so the gate cannot be
demonstrated through it. Tests use a non-root identity for that reason, not by preference.

## Related

- [gated-paths.md](./gated-paths.md)
- [evidence.md](./evidence.md)
