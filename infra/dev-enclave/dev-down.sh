#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# Stop the local enclave WITHOUT destroying state. The named volumes
# brieve-dev-vault-data and brieve-dev-pgdata are left alone deliberately: the raft
# store holds the trust configuration, and the Postgres volume holds run state.
#
# Destroying the Postgres volume also breaks dynamic credentials until rotate-root is
# re-run, because the database reverts to its bootstrap password while Vault still
# holds the rotated one. Removing volumes is therefore a deliberate act, not a flag here.

set -euo pipefail
say() { printf '\033[1m==>\033[0m %s\n' "$*"; }

say "Stopping Postgres (Nomad deallocates it; the container is disposable, the volume is not)"
nomad job stop -purge postgres >/dev/null 2>&1 || true

say "Stopping Vault (sealed on next start — unseal, never re-init)"
docker stop brieve-dev-vault >/dev/null 2>&1 || true

say "Stopping the Nomad dev agent"
pkill -f "nomad agent -dev" 2>/dev/null || true

cat <<'EOF'

  Enclave stopped. Nothing was destroyed.

    brieve-dev-vault-data   raft store — trust config, and the keys in .env unseal it
    brieve-dev-pgdata       run state

  Back up with: make dev-up
EOF
