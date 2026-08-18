#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# The one command that brings the local platform up on OrbStack / Docker Desktop.
#
#   stack.sh up [--no-surfaces]   enclave + dev-idp + MCP + portal (default)
#   stack.sh down                 stop everything, keep the data
#   stack.sh reset                stop everything and return to empty
#   stack.sh status               health across enclave and compose services
#
# Local Docker only. There is no --prod and no registry push — the enclave tree under
# infra/ is the whole deployment artifact this repository owns.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${HERE}/../.." && pwd)"
COMPOSE=(docker compose --env-file "${HERE}/.env.local" -f "${HERE}/docker-compose.yml")

# Seed the local config on first run — same discipline as inkantOS deploy/local.
if [[ ! -f "${HERE}/.env.local" ]]; then
  cp "${HERE}/.env.example" "${HERE}/.env.local"
  echo "created deploy/local/.env.local from .env.example — edit it to change ports"
fi

# shellcheck disable=SC1091
set -a; source "${HERE}/.env.local"; set +a

DEV_IDP_PORT="${DEV_IDP_PORT:-8090}"
MCP_SURFACE_PORT="${MCP_SURFACE_PORT:-8083}"
PORTAL_PORT="${PORTAL_PORT:-8082}"
DEV_IDP_URL="http://127.0.0.1:${DEV_IDP_PORT}"
MCP_URL="http://127.0.0.1:${MCP_SURFACE_PORT}/mcp"
PORTAL_URL="https://127.0.0.1:${PORTAL_PORT}/"

usage() { sed -n '2,14p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 2; }

die() {
  printf '\033[31m%s\033[0m\n' "$*" >&2
  exit 1
}

require_repo_env() {
  local key="$1" hint="$2"
  if [[ ! -f "${REPO}/.env" ]] || ! grep -q "^${key}=" "${REPO}/.env" 2>/dev/null; then
    die "${key} is not set in ${REPO}/.env — ${hint}"
  fi
}

check_prerequisites() {
  command -v docker >/dev/null || die "docker is not on PATH — start OrbStack or Docker Desktop"
  docker info >/dev/null 2>&1 || die "Docker is not running — start OrbStack or Docker Desktop"
  for bin in nomad vault terraform python3 uv; do
    command -v "$bin" >/dev/null || die "$bin is not on PATH — see docs/development/local-stack.md"
  done
  if ! docker run --rm --network host alpine:3 getent hosts host.docker.internal >/dev/null 2>&1; then
    die "host.docker.internal does not resolve inside a host-networked container.

  OrbStack and Docker Desktop provide it; plain Linux Docker does not. Scheduled workloads
  reach the trust store and state store by that name.

  Add it once:
      echo '127.0.0.1 host.docker.internal' | sudo tee -a /etc/hosts"
  fi
  require_repo_env VAULT_ENT_LICENSE "add your Vault Enterprise licence (never commit it)"
  if nc -z 127.0.0.1 5432 2>/dev/null; then
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -qv 'brieve'; then
      echo "warning: something is already listening on :5432 — brieve postgres binds there via Nomad host networking" >&2
      echo "         stop other local stacks (e.g. inkantos-local) before continuing" >&2
    fi
  fi
}

wait_for() {
  local label="$1" url="$2" deadline=$(( SECONDS + 120 ))
  printf 'waiting for %s' "$label"
  while (( SECONDS < deadline )); do
    if curl -fsS --max-time 2 "$url" >/dev/null 2>&1; then
      printf ' ok\n'; return 0
    fi
    printf '.'; sleep 1
  done
  printf ' TIMEOUT\n' >&2
  echo "  ${label} did not become healthy at ${url}" >&2
  echo "  logs: ${COMPOSE[*]} logs" >&2
  return 1
}

wait_for_tls() {
  local label="$1" url="$2" deadline=$(( SECONDS + 120 ))
  printf 'waiting for %s' "$label"
  while (( SECONDS < deadline )); do
    if curl -fsSk --max-time 2 "$url" >/dev/null 2>&1; then
      printf ' ok\n'; return 0
    fi
    printf '.'; sleep 1
  done
  printf ' TIMEOUT\n' >&2
  echo "  ${label} did not become healthy at ${url}" >&2
  echo "  try: nomad job status portal" >&2
  return 1
}

cmd_up() {
  local with_surfaces=1
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --no-surfaces) with_surfaces=0; shift ;;
      *) echo "unknown argument: $1" >&2; usage ;;
    esac
  done

  check_prerequisites

  cd "${REPO}"
  # Honour the listener's scheme, not a stale .env export. Fresh init writes http;
  # a half-finished TLS bootstrap leaves https — probing the wrong one reads as
  # "trust store is not answering" with no hint about the scheme.
  if [[ -f "${REPO}/infra/environments/dev/tls.auto.tfvars" && -f "${REPO}/.enclave/ca.pem" ]]; then
    export VAULT_ADDR="https://127.0.0.1:8200"
    export VAULT_CACERT="${REPO}/.enclave/ca.pem"
  else
    unset VAULT_ADDR VAULT_CACERT
  fi

  uv sync --extra adapters --extra surfaces --extra portal

  make dev-up

  "${COMPOSE[@]}" up -d --build
  wait_for "dev-idp" "${DEV_IDP_URL}/jwks"

  if [[ "$with_surfaces" -eq 1 ]]; then
    DEV_IDP=1 DEV_IDP_PORT="${DEV_IDP_PORT}" make mcp-surface-up
    wait_for "mcp-surface" "http://127.0.0.1:${MCP_SURFACE_PORT}/.well-known/oauth-protected-resource" || true

    DEV_IDP=1 DEV_IDP_PORT="${DEV_IDP_PORT}" make portal-up
    wait_for_tls "portal" "${PORTAL_URL}" || true
  fi

  echo
  echo "stack up (compose project: brieve-local):"
  echo "  enclave        make dev-status"
  echo "  trust store    see ${REPO}/.env VAULT_ADDR"
  echo "  scheduler      http://127.0.0.1:4646/ui/"
  echo "  state store    localhost:5432"
  echo "  dev identity   ${DEV_IDP_URL}"
  if [[ "$with_surfaces" -eq 1 ]]; then
    echo "  portal         ${PORTAL_URL}"
    echo "  MCP surface    ${MCP_URL}"
    echo
    echo "Connect a client:"
    echo '  { "mcpServers": { "brieve": { "url": "'"${MCP_URL}"'" } } }'
  else
    echo "  portal         not started (--no-surfaces)"
    echo "  MCP surface    not started (--no-surfaces)"
  fi
  if [[ -z "$(grep '^ASK_MODEL=' "${REPO}/.env" 2>/dev/null | cut -d= -f2- | tr -d '"')" ]]; then
    echo
    echo "note: ASK_MODEL is not set in .env — ask refuses before reaching a vendor."
    echo "      model-run-demo needs model-credentials/anthropic in Vault."
  fi
}

cmd_down() {
  nomad job stop -purge portal >/dev/null 2>&1 || true
  nomad job stop -purge api >/dev/null 2>&1 || true
  nomad job stop -purge mcp-surface >/dev/null 2>&1 || true
  "${COMPOSE[@]}" down
  make -C "${REPO}" dev-down
}

cmd_reset() {
  cmd_down
  docker volume rm brieve-dev-pgdata brieve-dev-vault-data 2>/dev/null || true
  rm -rf "${REPO}/.enclave" 2>/dev/null || true
  rm -f "${REPO}/infra/environments/dev/tls.auto.tfvars" 2>/dev/null || true
  rm -f "${REPO}/infra/environments/dev/terraform.tfstate" \
        "${REPO}/infra/environments/dev/terraform.tfstate.backup" 2>/dev/null || true
  echo "reset: enclave volumes, .enclave, TLS tfvars, and terraform state removed"
  echo "       delete VAULT_UNSEAL_KEY, VAULT_ROOT_TOKEN, and VAULT_ADDR from .env if bring-up refuses to unseal"
}

cmd_status() {
  make -C "${REPO}" dev-status
  echo
  "${COMPOSE[@]}" ps
  echo
  for probe in \
    "dev-idp ${DEV_IDP_URL}/jwks" \
    "mcp-surface http://127.0.0.1:${MCP_SURFACE_PORT}/.well-known/oauth-protected-resource" \
    "portal ${PORTAL_URL}"; do
    read -r label url <<< "$probe"
    curl_flags=(-fsS --max-time 2)
    [[ "$label" == portal ]] && curl_flags=(-fsSk --max-time 2)
    if body="$(curl "${curl_flags[@]}" "$url" 2>/dev/null)"; then
      echo "health ${label}: ${body:-ok}"
    else
      echo "health ${label}: UNREACHABLE"
    fi
  done
}

case "${1:-}" in
  up)     shift; cmd_up "$@" ;;
  down)   cmd_down ;;
  reset)  cmd_reset ;;
  status) cmd_status ;;
  *)      usage ;;
esac
