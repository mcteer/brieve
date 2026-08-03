# 016 — Task-scoped authority manufacture (parked, pruned)

**Parked by [ADR-0057](../../docs/adr/0057-context-hungry-agents-want-breadth-not-narrower-reads.md).**
Not abandoned, not unfinished, and not waiting for a volunteer — it was *answered*.

## Why it stopped

ADR-0056 established, by reading the substrate rather than inferring it, that Vault is the
OAuth **resource server** and cannot perform the RFC 8693 exchange. ADR-0057 then established
something larger: the read-scope narrowing this feature specifies is the wrong control for
these agents at all. They read widely before acting, so breadth of read is how the output gets
informed — and the property the narrowing was meant to buy (just-in-time, short-lived,
attested) is already held by per-allocation manufacture under a bounded TTL.

## What is here, and why only this

| Kept | Why |
| --- | --- |
| `research.md` | The expensive knowledge, and ADR-0057 requires it stay: Vault is the resource server; the entity binds through an alias on the agent-registry mount carrying `external_id` and `issuer`, which the typed Terraform resource cannot express; `jti` is mandatory and its absence reports only in Vault's server log while the caller sees a bare 403; `use_jwks` defaults true, so static keys need it set false explicitly. Whoever picks this up will not rediscover any of it. |
| `spec.md` | What was actually wanted. If write/act scopes ever enter a ceiling, this is the requirements framing to re-specify against. |

**Removed 2026-08-03**: `tasks.md`, `plan.md`, `data-model.md`, `quickstart.md`, `contracts/`,
`checklists/`. Execution scaffolding for work that will not be done as specified — and the task
list in particular read as fifty-one dropped obligations, which is the opposite of what
happened. All of it remains in git history if it is ever wanted.

## Where the built code went

Nineteen of fifty-one tasks were built and demonstrated. Those two commits are preserved as the
annotated tag **`archive/016-task-scoped-authority`**:

```sh
git show archive/016-task-scoped-authority
```

## What is still live

**RAR remains the mechanism for `write` and `act` scopes** — if those ever enter a ceiling.
They have not: agent ceilings grant read capabilities in the Vault secret space, and the
estate's writes reach products through [ADR-0044](../../docs/adr/0044-authz-doctrine-and-credential-translation.md)'s
federate-or-broker path rather than through Vault secret scopes, so there is nothing for RAR to
narrow. Resuming means re-specifying against that narrower question — not reviving this one.

ADR-0057 records the three triggers that would re-open the decision. Reaching for this work
without one of them means arguing with an Accepted record, which is a conversation to have in
the open under Principle X rather than a thing to route around.
