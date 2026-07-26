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
| Secrets engines the design may need are available | ✅ `kv`, `database`, `transit`, `pki`, `ssh`, `nomad`, `consul`, `aws`, `ldap`, `keymgmt` all mount |

No credential was placed in the jobspec. The workload authenticated as *itself*.

### Second pass — dynamic database credentials (2026-07-25)

The enclave is now persistent and the database path is real. `jobs/harness-probe.nomad.hcl`
runs the whole chain in one allocation:

| Claim | Result |
| --- | --- |
| A Nomad workload exchanges its identity for a Vault token | ✅ `auth/nomad/login` as role `harness`, ttl 300s |
| Vault mints a **per-request** Postgres credential | ✅ `database/creds/harness`, distinct user each read, lease 3600s |
| That credential actually opens a connection | ✅ `connected as v-nomad-ha-harness-…` |
| It can write, not only read | ✅ created a table and inserted through the dynamic role |
| The bootstrap password is **dead after rotate-root** | ✅ `password authentication failed for user "brieve"` — only Vault holds it |
| Postgres data survives a new allocation | ✅ job purged and re-run; rows intact on the named volume |
| Vault state survives container recreation | ✅ raft on `brieve-dev-vault-data`; unseal, do not re-initialise |

The jobspec is worth reading for what is *absent*: no password, no DSN, no token, no mounted
secret. The only thing the job is given is proof of who it is.

**One ordering consequence to internalise before debugging any of this**: the harness cannot
reach the database until it has an attested identity. A connection failure is therefore quite
often an identity failure one step earlier, and looking at Postgres first will waste your time.

## What it cost to find out

Four things were wrong in the first attempt. Three are constraints the production tree
inherits; the fourth turned out to be a licensing artifact and is recorded because the failure
mode is easy to misread:

1. **Vault Enterprise refuses `inmem` storage.** `vault server -dev` is therefore unusable with
   an Enterprise license — raft is required even for a throwaway. This is a stronger reason to
   avoid `-dev` than "it disables TLS".
2. **`2.0.3+ent` is a floor, not a version match.** The agent registry was introduced there. A
   `1.21-ent` image rejected the license outright (`invalid module: "platform-standard"`).
3. **Nomad's CPU fingerprint is wrong on Apple Silicon** — total reported as ~24 MHz while the
   core count is detected correctly. Any MHz-based resource request above that is unschedulable
   with `Dimension "cpu" exhausted`. Use `cores`.
4. **Nomad's docker driver refuses volume mounts by default.** A stateful task fails with
   `volumes are not enabled` and nothing pointing at the *agent* configuration as the fix —
   `nomad/client.hcl` here enables it. Any Nomad deployment scheduling a stateful workload
   inherits this, so it is not a dev-only wrinkle.
5. **A Docker named volume is owned by root; Vault runs as uid 100.** The server crash-loops on
   `permission denied` opening its own bolt file, with no hint that ownership is the cause. The
   fix is a chown, but *how* it is expressed matters: a `docker_container` that removes itself
   leaves Terraform holding an ID that no longer resolves and every later apply fails, and one
   that does not remove itself is permanent cruft in `docker ps -a`. A `terraform_data`
   provisioner keyed to the volume avoids both.
6. **`IPC_LOCK` must be written `CAP_IPC_LOCK`.** Docker normalises the name on read, so the
   short form is a permanent diff — and because capability changes force replacement, every
   `terraform apply` recreated the Vault container and **resealed it**. The symptom is an apply
   that half-succeeds with `Vault is sealed`, which reads like a race and is not one.
7. **Raft data is bound to `node_id`.** Moving a raft store to a Vault configured with a
   different `node_id` leaves the node outside its own peer set: it unseals, reports
   `HA Mode: standby` forever, and answers every API call with `Vault is sealed`. There is no
   error message connecting the two. Migrating a store means carrying the node ID with it.
8. **`.env` values are quoted**, and a naive `cut -d= -f2-` passes the quotes through. Vault
   rejected the license with `error decoding version: expected integer` — which does not sound
   like a quoting problem. Strip them.
9. **A license can silently constrain the architecture.** The first license carried a
   `pki-only` module, which is a *restriction* rather than a capability: `pki` mounted and every
   other secrets engine — `kv`, `database`, `transit`, `ssh`, `nomad`, `consul`, `aws`, `ldap`,
   `keymgmt` — was refused as *"not supported by license"*, while all auth methods worked. It
   was a provisioning artifact (selecting every module includes the restrictive one), and
   reissuing without `pki-only` opened all ten. **No constraint remains**, but the failure mode
   is worth knowing: a license that refuses secrets engines while permitting auth and identity
   looks like a scoped restriction, not a missing capability, and the module list is the place
   to check.

## Using it

Prerequisites and the reasoning behind them: [CONTRIBUTING.md](../../CONTRIBUTING.md).

```bash
make dev-up       # brings the whole stack up, in ADR-0048's order
make dev-status   # what is running
make dev-down     # stop, destroying nothing
```

`make dev-up` is idempotent — re-run it freely. It brings up Nomad (with the client config
that enables docker volumes), schedules Postgres, starts Vault, unseals it from `.env`, applies
the trust fabric and database engine, and verifies the chain by minting a credential.

**On a fresh machine** it initialises Vault and writes the unseal key and root token to `.env`.
On every later run it **unseals — it never re-initialises**, because re-initialising discards
the raft store and invalidates both values.

Prove the whole chain end to end:

```bash
nomad job run infra/dev-enclave/jobs/harness-probe.nomad.hcl
nomad alloc logs $(nomad job status harness | tail -1 | awk '{print $1}') probe
```

The manual sequence is in git history if you need it; `dev-up.sh` is the readable version.

### Two traps `dev-up` now handles for you

Both cost real time to diagnose, and both are silent until they are not:

1. **Never run Terraform against a sealed Vault.** The provider cannot read, so Terraform
   concludes every resource is gone and drops them from state. The next apply then tries to
   create mounts that already exist (`path is already in use`) and the provider can crash
   outright. `dev-up` refuses to apply until Vault is unsealed.
2. **`rotate-root` couples Vault and Postgres in both directions.** Destroy the Postgres volume
   and the database reverts to its bootstrap password while Vault holds the rotated one; disable
   Vault's database mount and Vault forgets the rotated password while Postgres still has it.
   Either way *nothing* can authenticate and the connection cannot be reconfigured. They must be
   reset together — which `dev-up` does automatically when it detects the drift.

Stopping the Vault container also drops it from Terraform state on the next refresh, so `dev-up`
re-imports it rather than trying to create a container whose name is taken.

## Deliberately missing

Everything that makes this a *dev* proof rather than the product's front door:

- **No HA.** Single Vault node, single Nomad server. Fencing and failover behaviour under
  partition are therefore *not* exercised — relevant to the durability feature, which asserts
  single-writer guarantees.
- **Nomad's own state is ephemeral.** `-dev` keeps nothing across restarts, so jobs must be
  re-run. The *data* survives on named volumes, which is the property durability needs; the
  scheduling does not.
- **No TLS.** Production uses the control plane's own CA (ADR-0025).
- **1-of-1 unseal.** A real deployment does not have a single unseal key sitting next to the
  server.
- **Root token retained.** The bootstrap root token still exists and never expires; it lives in
  the gitignored `.env` alongside the unseal key. ADR-0015's flow revokes it once configuration
  is applied, after which every caller authenticates through the attestation chain. Keeping it
  is what makes re-running `terraform apply` convenient here, and is exactly the shape that must
  not reach a deployment.
- **No parameterization for production.** The dev/prod split via a swappable substrate layer is
  the shape this points at, not one it implements.
