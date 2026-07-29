---
name: vault-secret-access
description: Read and write secrets in HashiCorp Vault using short-lived, task-scoped credentials. Use when an agent needs secret material, when choosing between static and dynamic secrets, or when a Vault operation is refused.
---

# Vault Secret Access

Read and write Vault secrets without ever holding a standing credential.

**Reference:** [Vault documentation](https://developer.hashicorp.com/vault/docs)

## Authenticate as the workload, never as a person

Every Vault operation authenticates with the identity the platform already attested — a
workload identity issued to this allocation. There is no token to store, copy, or pass.

- Do **not** ask for a token, request one from a person, or read one from configuration.
- Do **not** reuse a credential across tasks. A credential is scoped to the task that
  manufactured it and expires with it.
- If authentication fails, the correct response is to report it, not to seek another route.

```bash
# The workload's own identity. No secret is supplied.
vault write auth/jwt/login role=agent-run jwt="$WORKLOAD_JWT"
```

## Prefer dynamic secrets over static ones

| Kind | Use when | Lifetime |
|------|----------|----------|
| Dynamic (`database/creds/<role>`) | The target supports it | Minutes; revoked on lease expiry |
| Static KV (`kv/data/<path>`) | The target cannot issue credentials | Until rotated |

A dynamic secret that expires mid-task is working correctly. Re-request it; do not cache
it, and do not extend its lease to avoid re-requesting.

```bash
# Good — dynamic, short-lived, attributable to this task
vault read database/creds/app-readonly

# Only when the target cannot issue its own
vault kv get -mount=kv app/config
```

## Never place secret material where it will persist

Secret **values** must not enter logs, checkpoints, run records, tool arguments, commit
messages, or model context. References may.

- Pass a path (`kv/data/app/config`), not the value at that path.
- When a value must be used, use it and discard it. Do not summarise it, echo it back for
  confirmation, or include it in a report.
- Redact before writing anywhere durable. A secret written to an append-only record is
  permanent.

```bash
# Bad — the value lands in shell history and any log capturing stdout
export DB_PASSWORD=$(vault kv get -field=password kv/app/db)
echo "using $DB_PASSWORD"

# Good — the value is consumed by the process that needs it and never printed
vault kv get -field=password kv/app/db | psql-connect --password-stdin
```

## Read what you need, not what you can reach

Request the narrowest path that satisfies the task. A read of `kv/data/app/db` is
attributable; a read of `kv/data/*` is a question nobody can answer afterwards.

## When Vault refuses

Vault distinguishes two failures that look similar and mean opposite things.

| Response | Meaning | Correct action |
|----------|---------|----------------|
| `403 permission denied` | The path exists or may exist; this identity may not read it | Report the refusal. Do not retry, and do not try adjacent paths |
| `404 not found` | No secret at this path, and you were permitted to look | Report that the secret is absent |

**A permission denial is a boundary, not an obstacle.** Do not probe neighbouring paths,
re-authenticate as something else, or look for an alternative route to the same value. If
the task genuinely requires the secret, report what was refused and stop.

Note that a path with **no read grant at all** answers `403`, not `404` — so "not
permitted" and "does not exist" are indistinguishable to the caller by design. When
diagnosing, check the policy before concluding the secret is missing.

## Writing

- Write to a path the task was scoped to and no other.
- Use CAS (check-and-set) so a concurrent write fails rather than silently overwriting.
- Never write a secret you were given to read elsewhere.

```bash
vault kv put -cas=3 -mount=kv app/config api_endpoint=https://example.internal
```

## Checklist

- [ ] Authenticated as the workload, not with a supplied token
- [ ] Dynamic secret used where the target supports one
- [ ] Narrowest path requested
- [ ] No secret value in logs, arguments, records, or output
- [ ] Refusals reported rather than routed around
- [ ] Writes scoped and CAS-guarded

---

*Authored for the brieve capability pack in the open Agent Skills format, intended for
contribution to [`hashicorp/agent-skills`](https://github.com/hashicorp/agent-skills).*
