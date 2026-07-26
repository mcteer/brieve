# Quickstart validation: Deployment Module Tree

**Feature**: `specs/006-deployment-module-tree`
**Purpose**: Prove FR-001–FR-016 after `feat/006-deployment-module-tree` lands.
**Not**: an implementation guide (see `tasks.md`).

Contracts: [module-interface](./contracts/module-interface.md),
[bring-up-contract](./contracts/bring-up-contract.md),
[substrate-requirements](./contracts/substrate-requirements.md).
Model: [data-model](./data-model.md).

## Prerequisites

- Docker, Terraform ≥ 1.9, Nomad, Vault CLI, `uv`
- `.env` with the Vault Enterprise licence (2.0.3+ent is a floor, not a preference — the agent
  registry was introduced there)
- **No prior enclave required.** If one exists from `infra/dev-enclave`, Scenario F covers the
  migration

## Scenario A — Bring-up delivers its contract (US3)

```bash
make dev-up
make dev-status
```

**Expect**: every guarantee in [bring-up-contract](./contracts/bring-up-contract.md) holds and was
*checked*, not assumed — scheduler up, trust store unsealed and active, trust fabric configured, a
dynamic credential minted and authenticating, state store migrated, volumes intact.

## Scenario B — A missing prerequisite is named (US3)

```bash
# Stop Docker, or remove the licence from .env
make dev-up
```

**Expect**: failure naming the missing prerequisite. Not "bring-up failed" — the tool knows which
part is absent, and withholding that costs the reader the diagnosis it already did.

## Scenario C — Re-running destroys nothing (US3, FR-009)

```bash
make dev-up      # against an environment already up
```

**Expect**: success, no state change, and **no re-initialisation** of the trust store. Verify the
credentials in `.env` still unseal it. Re-initialising would discard the store and invalidate every
credential derived from it.

## Scenario D — One tree, two substrates (US1) 🎯 the feature

```bash
cd infra/environments/dev        && terraform plan -out=dev.plan
cd ../production                 && terraform plan -out=prod.plan
make enclave-digest-diff
```

**Expect**: identical configuration digests — auth methods, roles, policies, secrets engines,
registry entries, database roles (SC-001). Needs no customer infrastructure: the comparison is over
the configuration the tree *produces*, which is why this criterion will actually get run.

**Also expect**: the only differing files between the two roots are substrate composition and
profile. If a trust setting differs, the delta has escaped its layer and
[module-interface](./contracts/module-interface.md) invariant 1 or 2 has been broken.

## Scenario E — Conformance under a real attested identity (US2) 🎯 the gap 005 left

```bash
make conformance
```

**Expect**: the durability rows run **inside a scheduled allocation**, the workload presents its own
identity, and its state-store credential was minted for that identity.

```bash
grep -rn "DevVaultCredentials" tests/ ; echo "exit=$?"
```

**Expect**: no matches (SC-003). Deleted, not bypassed — while it exists, someone can reach for it.

```bash
# Run the suite outside an allocation
uv run pytest tests/conformance/durability -q
```

**Expect**: failure naming the absent workload identity. No fallback path (SC-004, FR-007).

## Scenario F — The proof directory is gone (FR-015, SC-010)

```bash
ls infra/dev-enclave 2>&1
```

**Expect**: absent. Exactly one supported way to stand up an environment exists.

**Also expect**: its failure catalogue survived the deletion — the six recorded traps appear in the
tree's documentation. That knowledge was the most expensive thing the proof produced.

## Scenario G — Production posture is answered (US4, FR-010)

Review the four items in [data-model](./data-model.md#productionpostureitem):

| Item | Expect |
| --- | --- |
| Transport security | **Implemented** — PKI-issued certificates, self-signed bootstrap |
| Bootstrap credential | **Implemented** for the production profile; retained in development, deliberately |
| Unseal shape | **Seam only** — `seal_config` accepts a production configuration without editing the module |
| High availability | **Deferred**, with a reason and a named trigger |

**Expect**: no item silently absent. Deferral is acceptable; silence is the failure FR-010 exists to
prevent.

## Scenario H — Recorded traps report causes (US5, FR-013)

For each catalogue entry, induce the condition and read the message.

**Expect**: it names the **cause**, not the symptom — ownership rather than storage, node identity
rather than the seal, the seal rather than the configuration, the credential coupling rather than
the credential path. These are catalogued precisely because their symptoms point elsewhere.

## Full gate

```bash
make check          # hermetic
make conformance    # requires the enclave; now runs in an allocation
```

Both green is the completion bar.
