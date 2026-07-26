#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# Bring up the local enclave in ADR-0048's order: Terraform -> Vault -> Nomad -> harness.
# Idempotent: safe to re-run when parts are already up.
#
# What it will NOT do: re-initialise a Vault that already has a raft store. That would
# discard everything and invalidate the credentials in .env, and it is the single most
# expensive mistake available here.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENCLAVE_DIR="$REPO_ROOT/infra/dev-enclave"
ENV_FILE="$REPO_ROOT/.env"
export VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
NOMAD_ADDR="${NOMAD_ADDR:-http://127.0.0.1:4646}"

say()  { printf '\033[1m==>\033[0m %s\n' "$*"; }
ok()   { printf '    \033[32mok\033[0m %s\n' "$*"; }
die()  { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

# .env values are quoted. A naive `cut -d= -f2-` passes the quotes through, and Vault
# then rejects the license with "error decoding version: expected integer" — which does
# not sound like a quoting problem and costs an hour to find.
env_val() {
  [ -f "$ENV_FILE" ] || die ".env not found at $ENV_FILE"
  grep "^$1=" "$ENV_FILE" | head -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//'
}

env_set() {
  local key="$1" val="$2"
  if grep -q "^$key=" "$ENV_FILE" 2>/dev/null; then
    # Written via python to avoid sed portability pain and to keep the value off argv.
    KEY="$key" VAL="$val" python3 - "$ENV_FILE" <<'PY'
import os, re, sys
p = sys.argv[1]
k, v = os.environ["KEY"], os.environ["VAL"]
t = open(p).read()
open(p, "w").write(re.sub(rf'^{k}=.*$', f'{k}="{v}"', t, flags=re.M))
PY
  else
    printf '%s="%s"\n' "$key" "$val" >> "$ENV_FILE"
  fi
}

# ---------------------------------------------------------------- preflight

say "Preflight"
for bin in docker nomad vault terraform python3; do
  command -v "$bin" >/dev/null || die "$bin not found on PATH. See CONTRIBUTING.md."
done
docker info >/dev/null 2>&1 || die "Docker is not running. Start Docker Desktop."
LICENSE="$(env_val VAULT_ENT_LICENSE)"
[ -n "$LICENSE" ] || die "VAULT_ENT_LICENSE missing from .env"
ok "tooling present, Docker running, license found (${#LICENSE} chars)"

# ---------------------------------------------------------------- 1. Nomad

# Nomad first: Vault fetches Nomad's JWKS at configure time, and Nomad schedules Postgres.
say "Nomad"
if curl -sf -o /dev/null --max-time 3 "$NOMAD_ADDR/v1/status/leader"; then
  ok "already running"
else
  # -config enables docker volume mounts, which the driver refuses by default. A
  # stateful task without it fails with `volumes are not enabled` and nothing in the
  # message points at the agent's configuration as the fix.
  nohup nomad agent -dev -bind 0.0.0.0 -config="$ENCLAVE_DIR/nomad/client.hcl" \
    > "${TMPDIR:-/tmp}/brieve-nomad.log" 2>&1 &
  for _ in $(seq 1 30); do
    curl -sf -o /dev/null --max-time 2 "$NOMAD_ADDR/v1/status/leader" && break
    sleep 1
  done
  curl -sf -o /dev/null --max-time 2 "$NOMAD_ADDR/v1/status/leader" \
    || die "Nomad did not come up. Log: ${TMPDIR:-/tmp}/brieve-nomad.log"
  ok "started (log: ${TMPDIR:-/tmp}/brieve-nomad.log)"
fi

# ---------------------------------------------------------------- 2. Postgres

say "Postgres"
cd "$ENCLAVE_DIR"
if nomad job status postgres 2>/dev/null | grep -q "^Status *= *running"; then
  ok "job already running"
else
  nomad job run jobs/postgres.nomad.hcl >/dev/null
  ok "job submitted"
fi
for _ in $(seq 1 60); do
  nc -z 127.0.0.1 5432 2>/dev/null && break
  sleep 1
done
nc -z 127.0.0.1 5432 2>/dev/null || die "Postgres not listening on 5432. Try: nomad job status postgres"
ok "listening on 5432 (data on volume brieve-dev-pgdata, survives the allocation)"

# ---------------------------------------------------------------- 3. Vault container

say "Vault"
export TF_VAR_vault_license="$LICENSE"
[ -d .terraform ] || terraform init -input=false >/dev/null

# Stopping the container makes the Docker provider drop it from state on the next
# refresh, so a plain apply then tries to CREATE a container whose name is taken and
# fails with a Conflict. Reconcile before applying: start what exists, and re-import it
# if Terraform has forgotten it. Without this, every stop/start cycle wedges the stack.
if docker container inspect brieve-dev-vault >/dev/null 2>&1; then
  docker start brieve-dev-vault >/dev/null 2>&1 || true
  if ! terraform state list 2>/dev/null | grep -qx 'docker_container.vault'; then
    terraform import -input=false -var vault_token=placeholder \
      docker_container.vault "$(docker container inspect -f '{{.ID}}' brieve-dev-vault)" >/dev/null \
      && ok "re-imported the existing Vault container into Terraform state"
  fi
fi

terraform apply -input=false -auto-approve \
  -target=docker_container.vault -var vault_token=placeholder >/dev/null
for _ in $(seq 1 30); do
  curl -sf -o /dev/null --max-time 2 "$VAULT_ADDR/v1/sys/seal-status" && break
  sleep 1
done
curl -sf -o /dev/null --max-time 2 "$VAULT_ADDR/v1/sys/seal-status" \
  || die "Vault container is not answering. Try: docker logs brieve-dev-vault"

INITIALIZED="$(vault status -format=json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["initialized"])' || echo False)"
if [ "$INITIALIZED" = "False" ]; then
  say "Vault is uninitialised — first run"
  INIT_JSON="$(vault operator init -key-shares=1 -key-threshold=1 -format=json)"
  UNSEAL="$(printf '%s' "$INIT_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["unseal_keys_b64"][0])')"
  ROOT="$(printf '%s' "$INIT_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["root_token"])')"
  env_set VAULT_UNSEAL_KEY "$UNSEAL"
  env_set VAULT_ROOT_TOKEN "$ROOT"
  ok "initialised; unseal key and root token written to .env (1-of-1: dev only)"
else
  ok "already initialised — unsealing, not re-initialising"
fi

if vault status 2>/dev/null | grep -q "^Sealed *false"; then
  ok "already unsealed"
else
  vault operator unseal "$(env_val VAULT_UNSEAL_KEY)" >/dev/null \
    || die "Unseal failed. Is VAULT_UNSEAL_KEY in .env the key for volume brieve-dev-vault-data?"
  ok "unsealed"
fi
for _ in $(seq 1 20); do
  vault status 2>/dev/null | grep -q "^HA Mode *active" && break
  sleep 1
done

# ---------------------------------------------------------------- 4. Trust fabric

# NEVER run Terraform against a sealed Vault. The provider cannot read, so Terraform
# concludes the resources are gone and drops them from state — after which the next
# apply tries to create mounts that already exist ("path is already in use") and the
# provider can crash outright. The unseal above is a hard precondition for this step.
vault status 2>/dev/null | grep -q "^Sealed *false" \
  || die "Vault is sealed; refusing to run Terraform against it (it would corrupt state)."

say "Trust fabric and database engine"
if ! terraform apply -input=false -auto-approve -var vault_token="$(env_val VAULT_ROOT_TOKEN)" >/dev/null 2>&1; then
  # Most often: Terraform state and Vault disagree after an interrupted run. Vault's
  # configuration is entirely declarative here, so rebuilding it is cheap and safe —
  # unlike the raft init, which holds the keys in .env and is never touched.
  say "Apply failed — reconciling Vault configuration and retrying"
  export VAULT_TOKEN="$(env_val VAULT_ROOT_TOKEN)"
  vault auth disable nomad    >/dev/null 2>&1 || true
  vault secrets disable database >/dev/null 2>&1 || true
  vault policy delete agent-ceiling-demo >/dev/null 2>&1 || true
  vault policy delete harness-database   >/dev/null 2>&1 || true
  vault delete identity/entity/name/demo-agent >/dev/null 2>&1 || true

  # Disabling the database mount discards Vault's memory of the rotated root password
  # while Postgres still has it, so nothing can authenticate and the connection cannot
  # be reconfigured. The two are coupled by rotate-root and must be reset together.
  # Only the checkpoint store is lost, and a reconcile means it was already unusable.
  say "Resetting Postgres (rotate-root couples it to the database mount)"
  nomad job stop -purge postgres >/dev/null 2>&1 || true
  sleep 5
  docker volume rm brieve-dev-pgdata >/dev/null 2>&1 || true
  nomad job run jobs/postgres.nomad.hcl >/dev/null 2>&1 || true
  for _ in $(seq 1 60); do nc -z 127.0.0.1 5432 2>/dev/null && break; sleep 1; done
  sleep 5

  terraform apply -input=false -auto-approve -var vault_token="$(env_val VAULT_ROOT_TOKEN)" >/dev/null \
    || die "Apply still failing after reconcile. Run it by hand for the real error:
       cd infra/dev-enclave && terraform apply -var vault_token=..."
fi
ok "JWT auth, agent registry, ceiling policies, database engine, dynamic role"

# ---------------------------------------------------------------- 5. Verify

say "Verifying the chain"
CREDS="$(VAULT_TOKEN="$(env_val VAULT_ROOT_TOKEN)" vault read -format=json database/creds/harness 2>/dev/null)" \
  || die "Could not mint a database credential. If the Postgres volume was destroyed, the
       database is back on its bootstrap password while Vault holds the rotated one. Fix:
       terraform apply -replace=vault_generic_endpoint.rotate_root -var vault_token=..."
DBUSER="$(printf '%s' "$CREDS" | python3 -c 'import json,sys; print(json.load(sys.stdin)["data"]["username"])')"
ok "Vault minted a Postgres credential ($DBUSER)"

cat <<EOF

  Enclave up.

    Vault    $VAULT_ADDR   (unsealed, agent registry + database engine configured)
    Nomad    $NOMAD_ADDR
    Postgres 127.0.0.1:5432  (scheduled by Nomad, data on brieve-dev-pgdata)

  Credentials are Vault-minted per workload — there is no database password to export.
  Prove the full chain end to end:

    nomad job run infra/dev-enclave/jobs/harness-probe.nomad.hcl

  Stop without destroying anything:  make dev-down
EOF
