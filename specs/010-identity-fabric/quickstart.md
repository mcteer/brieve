# Quickstart: validating the production identity fabric

**Feature**: `specs/010-identity-fabric` | **Date**: 2026-07-28

How to prove this feature works, end to end, against a live enclave. Every command here is
runnable today except those marked **(after implementation)**; the ones that run now are
what Phase 0 used to reach its findings, and re-running them is how you check the ground has
not moved.

## Prerequisites

```bash
make dev-up          # the enclave must be RUNNING, not assumed
make dev-status      # trust store, scheduler, state store
```

The trust fabric must be unsealed and serving. Every command below authenticates to it;
`enclave-up` writes `VAULT_ADDR`, `VAULT_CACERT`, and the root token to `.env`.

```bash
export VAULT_ADDR=$(grep '^VAULT_ADDR=' .env | cut -d= -f2- | tr -d '"')
export VAULT_CACERT=$(grep '^VAULT_CACERT=' .env | cut -d= -f2- | tr -d '"')
export VAULT_TOKEN=$(grep '^VAULT_ROOT_TOKEN=' .env | cut -d= -f2- | tr -d '"')
```

## 1 — Confirm the registry is readable *(runs today)*

The premise the whole feature rests on. If this fails, the plan is wrong rather than the code.

```bash
vault list agent-registry/registration/display-name
vault read -format=json agent-registry/registration/display-name/demo-agent
```

**Expect**: `demo-agent` listed, and a record with `ceiling_policies`, `entity_id`, `owner`.

**Also expect, and do not be alarmed by**: `ceiling_policies` contains three entries when
Terraform declared one. Vault appends `default` and `default-ceiling` (research Finding 2).
A reader seeing only its own declaration would be reading something that does not exist.

## 2 — Confirm the fixture problem is real *(runs today)*

```bash
vault policy read agent-ceiling-demo          # -> path "secret/data/demo/*"
vault secrets list | grep '^secret/' || echo "secret/ is NOT mounted"
```

**Expect**: the policy grants a path under a mount that does not exist. This is why a new
fixture precedes every enclave row — assertions against `demo-agent` pass whether enforcement
works or not.

## 3 — Read a ceiling record *(after implementation)*

```bash
vault kv get -format=json <mount>/harness-ceilings/terraform-agent
```

**Expect**: `schema_version`, `tool_names`, `product_actions`. This is the record the fabric
reads, in the core's own vocabulary — no paths, no translation.

## 4 — Prove the ceiling reaches a running agent *(after implementation)*

The end-to-end assertion, and the one SC-002 names.

```bash
make conformance          # includes tests/conformance/identity/
```

**Expect**: two definitions with different ceilings produce different manufactured authority,
and neither exceeds its record. Run inside an allocation under an attested identity — not on
the host, and not against a recorded response.

## 5 — Prove the negative: a tool cannot read a ceiling *(after implementation)*

FR-016, and the row that asserts Vault refuses rather than our code refusing.

```bash
# with an agent's own credential, not the root token
VAULT_TOKEN=$AGENT_TOKEN vault kv get <mount>/harness-ceilings/terraform-agent
```

**Expect**: `permission denied`, from the trust fabric. A refusal produced by our code would
satisfy the behaviour and miss the point — ADR-0015 puts the fabric structurally outside
every agent ceiling, and "structurally" means the denial is not ours to make.

## 6 — Prove a mid-run outage suspends and recovers *(after implementation)*

The longest scenario, and the one that exercises the circularity in the plan.

```bash
# 1. start a long run
# 2. seal the trust store:            vault operator seal
# 3. observe: the run SUSPENDS naming trust-fabric, and its container ends
# 4. unseal:                          vault operator unseal "$(grep VAULT_UNSEAL_KEY .env | ...)"
# 5. observe, in this order and no other:
#      health checker login succeeds
#      -> checker obtains database credentials
#      -> checker records trust-fabric healthy
#      -> sweeper resumes the run in a NEW allocation with a NEW identity
```

**Expect**: zero operator actions between step 4 and the run completing. If anything has to
be pressed, ADR-0049 has been violated by this feature rather than upheld by it.

**Watch for the trap**: sealing the trust store is also how the enclave breaks in ways that
are not this test. `infra/dev-enclave/README.md` records that Terraform run against a sealed
Vault drops every resource from state and the next apply crashes the provider. Do not run
`terraform apply` while sealed for this scenario.

## 7 — The rows that need no enclave *(after implementation)*

```bash
make check                    # protocol shape, reason codes, no src -> tests imports
make conformance-hermetic     # the fork-safe subset
```

**Expect**: the protocol declares no test-only method, no module under `src/` imports from
`tests/`, and the three "no scope" cases produce three distinct reason codes.

## What a passing run does NOT prove

- **That authority manufacture matches the constitution.** Principle IV describes RFC 8693 +
  RAR; the implementation is a JWT role login. These checks prove the ceiling is read and
  enforced, not that it is manufactured as described (research Finding 5).
- **That the two jurisdictions agree.** An agent can hold a tool whose secrets it cannot
  read. Legal, and nothing reports it.
- **That this works against a real IdP.** One identity source is exercised, not the variety
  a customer will have.
