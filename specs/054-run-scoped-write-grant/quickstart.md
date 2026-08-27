# Quickstart: reproducing and validating 054

**Date**: 2026-08-27 | **Spec**: [spec.md](spec.md)

## Prerequisites

```bash
uv sync --all-extras     # NOT --extra <one>, which REPLACES installed extras
make dev-up
```

Enclave coordinates come from `.env` (`VAULT_ADDR`, `VAULT_CACERT`, `VAULT_ROOT_TOKEN`), the
same way `make conformance` sources them.

## 1. Reproduce the defect (before the fix)

Mint a token carrying exactly what the `agent-run` role grants, then act on a policy that
belongs to a different run. On 2026-08-27 this returned **200, 200, 204**.

```bash
# a token shaped like a dispatched run's
curl -sk -X POST -H "X-Vault-Token: $VAULT_TOKEN" \
  -d '{"policies":["harness-authority-read","agent-pack-secrets","harness-database","scratch-policy-check"],"ttl":"10m","no_parent":true}' \
  "$VAULT_ADDR/v1/auth/token/create"
```

Then read, write and delete `sys/policies/acl/scratch-agent-<some-other-run>-current` with it.
**Clean up anything you seed** — the namespace is swept, but a leftover policy is noise in a
store other rows read.

After the fix, the same three attempts must be refused. That is rows E1–E3.

## 2. Confirm R1 for yourself — why templating was rejected

The finding that shaped this plan, and it is two commands:

```bash
curl -s http://127.0.0.1:4646/v1/jobs        # dispatch ids ARE unique per run
```

```bash
# ...but every run shares one alias, because the identity presents the PARENT job id
for id in $(curl -sk -H "X-Vault-Token: $VAULT_TOKEN" -X LIST \
    "$VAULT_ADDR/v1/identity/entity-alias/id" | python3 -c \
    "import sys,json;print(' '.join(json.load(sys.stdin)['data']['keys']))"); do
  curl -sk -H "X-Vault-Token: $VAULT_TOKEN" "$VAULT_ADDR/v1/identity/entity-alias/id/$id"
done
```

Six aliases, named by role. `auth.tf` records why at the `agent_run` role.

## 3. Settle R2 before building anything

The question that decides this feature's cost: does Nomad 2.0.4's workload identity JWT carry
a per-allocation claim, and can `user_claim` point at it?

If yes, the feature is a changed `user_claim` plus a templated policy. If no, the fallback is
constrained by ADR-0058 and 016's substrate is the answer. **Do not build the substrate before
this is answered** — see [research.md](research.md) R2.

## 4. Run the gates

```bash
make check                # hermetic: derivation, re-mint stability, refusal codes
make conformance          # the live rows — E1..E7 fail loudly if the enclave is absent
```

## What "done" looks like

- The three attempts in §1 are refused, and the same authority still writes its own workspace
- Removing the narrowing makes the refusal rows pass again (E5) — the safety case can lose
- A run with no declared write path holds no write authority at all (A1)
- A re-mint reproduces the recorded scope; a widened one is refused **and detectable** (A3, A4)
- No derived workspace contains a wildcard (A10)
- Reads unchanged (E6); the sweeper still lists (E7)
