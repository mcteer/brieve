# Dev enclave — validation proof

**Status: proof, not the production module tree.** This exists to demonstrate that
[ADR-0048](../../docs/adr/0048-nomad-is-the-agent-execution-substrate.md)'s claims hold before
that ADR is treated as settled — Principle IX, evidence over claims. The production-shaped,
parameterized tree is the local-environment feature on the [roadmap](../../ROADMAP.md), and it
should be *specified*, not grown from this directory by inertia.

What is durable here is the **trust configuration** in `vault-trust.tf`. It is written to apply
unchanged against a production Vault; only `substrate.tf` is expected to be replaced.

## What this proved

Run against Vault Enterprise 2.0.3+ent and Nomad 2.0.4 on 2026-07-25.

| Claim | Result |
| --- | --- |
| Nomad issues an attestable workload identity | ✅ RS256 JWKS at `/.well-known/jwks.json`; 812-char JWT delivered to the task |
| Vault verifies it with no shared secret | ✅ JWT auth backend configured from Nomad's JWKS URL alone |
| The exchange yields a **ceiling-scoped, short-lived** token | ✅ `policies: ["agent-ceiling-demo","default"]`, `lease_duration: 300` |
| Vault has a first-class **agent registry** | ✅ `/agent-registry/register` with `ceiling_policies`, `entity_id`, lookup by id or display name |
| Bootstrap order terminates | ✅ Terraform → Vault → Nomad → harness |

No credential was placed in the jobspec. The workload authenticated as *itself*.

## What it cost to find out

Four things were wrong in the first attempt, and each is a constraint the production tree
inherits:

1. **Vault Enterprise refuses `inmem` storage.** `vault server -dev` is therefore unusable with
   an Enterprise license — raft is required even for a throwaway. This is a stronger reason to
   avoid `-dev` than "it disables TLS".
2. **`2.0.3+ent` is a floor, not a version match.** The agent registry was introduced there. A
   `1.21-ent` image rejected the license outright (`invalid module: "platform-standard"`).
3. **Nomad's CPU fingerprint is wrong on Apple Silicon** — total reported as ~24 MHz while the
   core count is detected correctly. Any MHz-based resource request above that is unschedulable
   with `Dimension "cpu" exhausted`. Use `cores`.
4. **This license is module-limited.** `pki` mounts; `kv-v2`, `database`, `transit`, and
   `spiffe` are rejected as *"not supported by license"*. Anything the platform builds on those
   engines needs either a different license or a different design — worth settling before a
   feature depends on one.

## Using it

Prerequisites and the reasoning behind them: [CONTRIBUTING.md](../../CONTRIBUTING.md).

```bash
# 1. Nomad must be running first — Vault fetches its JWKS at configure time.
nomad agent -dev -bind 0.0.0.0

# 2. Apply. The license comes from the gitignored .env; it is never committed
#    and never passed on a command line.
export TF_VAR_vault_license="$(grep '^VAULT_ENT_LICENSE=' ../../.env | cut -d= -f2-)"
terraform init
terraform apply -var vault_token=<root-token>
```

Vault starts sealed because it uses raft. Initialise and unseal it once before applying the
trust configuration; keep the unseal material out of the repository.

```bash
export VAULT_ADDR=http://127.0.0.1:8200
vault operator init -key-shares=1 -key-threshold=1   # dev only — never this shape in production
vault operator unseal <key>
```

Then schedule Postgres:

```bash
nomad job run jobs/postgres.nomad.hcl
```

## Deliberately missing

Everything that makes this a *dev* proof rather than the product's front door:

- **No HA.** Single Vault node, single Nomad server. Fencing and failover behaviour under
  partition are therefore *not* exercised — relevant to the durability feature, which asserts
  single-writer guarantees.
- **No TLS.** Production uses the control plane's own CA (ADR-0025).
- **1-of-1 unseal.** A real deployment does not have a single unseal key sitting next to the
  server.
- **No parameterization for production.** The dev/prod split via a swappable substrate layer is
  the shape this points at, not one it implements.
