# SPDX-License-Identifier: Apache-2.0
#
# The MCP surface, served — 019, closing ROADMAP gap 0f.
#
# Separate from `mcp.nomad.hcl`, which runs the supervisory loop (health checks, the
# sweeper, audit egress). **FR-015a requires them to be independently available**, and two
# jobs satisfy that structurally rather than by catching everything: a crash in protocol
# framing cannot stop suspended runs from resuming if the two are not the same process.
# That is ADR-0025's preference generally — structure over runtime care.
#
# READ THIS JOBSPEC FOR WHAT IS ABSENT: no token, no password, no DSN, no mounted secret.
# The service presents its workload identity and receives what it is entitled to.

variable "vault_addr" {
  type        = string
  default     = "https://host.docker.internal:8200"
  description = <<-DESC
    Where the trust store answers, AS SEEN FROM THIS CONTAINER.

    `host.docker.internal`, not loopback, and unlike the host-mode jobs this is not
    interchangeable. This task runs in BRIDGE mode (see below), so `127.0.0.1` is the
    container itself. The trust store publishes `0.0.0.0:8200`, so it is reachable at the
    Docker host name — and its certificate carries `DNS:host.docker.internal`, which
    `infra/modules/trust-fabric/pki.tf` put there for exactly this class of caller.
  DESC
}

variable "vault_cacert" {
  type        = string
  default     = "/src/.enclave/ca.pem"
  description = "Control-plane CA as seen inside the container, read from the live mount."
}

variable "nomad_addr" {
  type        = string
  default     = "http://host.docker.internal:4646"
  description = <<-DESC
    Where the scheduler is, from in here. Starting a run dispatches, so this is load-bearing.

    014 paid for this once: the sweeper's dispatcher defaulted to a loopback that was correct
    for a host process and wrong for an allocation, and every resume failed `Connection
    refused` where nobody was watching.
  DESC
}

variable "db_host" {
  type        = string
  default     = "host.docker.internal"
  description = <<-DESC
    Where the database answers, AS SEEN FROM THIS CONTAINER.

    The host-mode services reach it at `127.0.0.1` because they share the Docker VM's
    namespace. This one does not. Postgres publishes `127.0.0.1:5432` on the developer's
    machine, which from a bridge container is `host.docker.internal`.

    **Passed to the collaborators at construction — no `src/core/` module changes.** Every
    Postgres collaborator already accepts `host`; the seam existed and was unused.
  DESC
}

variable "oidc_issuer" {
  type        = string
  description = "The issuer this surface verifies callers against. Required — it will not start without one."
}

variable "oidc_jwks_uri" {
  type = string
}

variable "oidc_audience" {
  type    = string
  default = "harness-api"
}

variable "oidc_tenant_claim" {
  type    = string
  default = "tenant"
}

variable "authority_controlled_path" {
  type        = string
  default     = "harness-authority/data/claim-mappings"
  description = "The gated path claim mappings are read from and changes written to."
}

variable "surface_port" {
  type        = string
  default     = "8083"
  description = "Where the protocol answers. Published to the developer's machine — that is the point."
}

variable "repo" {
  type = string
}

variable "harness_started_by" {
  type    = string
  default = ""
  description = <<-DESC
    Set by the deployment lane to claim ownership of a surface it started.

    Empty when a person brings it up themselves — their surfaces carry no mark and the lane
    will never stop them (017, FR-007a).
  DESC
}

job "mcp-surface" {
  # 017's deployment lane. Every job definition must be a declared subject or an explicitly
  # excluded one — coverage a process opts into is fail-open, and the process nobody
  # remembered to enrol is exactly the one nobody remembered to cover.
  meta {
    harness_surface     = "true"
    harness_shape       = "served"
    harness_covered_by  = "tests/conformance/mcp_served/test_a_client_reaches_the_surface.py"
    # FALSE, because the DEPLOYMENT lane does not own this surface — 019's own
    # `infra/bin/mcp-surface-conformance` starts and stops it, and it needs a development
    # identity provider standing before the surface starts at all.
    #
    # Set to "true" first, which told the deployment lane to bring it up: CI reported
    # "Standing up: api mcp-surface portal" and then failed `declared but unasserted`,
    # because a surface a lane starts must be asserted by a row in THAT lane. The gate was
    # right and the declaration was wrong — two lanes cannot both own one process's
    # lifecycle, and the second would have been starting it without its provider.
    harness_lane_starts = "false"
    harness_started_by  = var.harness_started_by
  }

  type = "service"

  group "mcp-surface" {
    count = 1

    network {
      port "protocol" {
        static = 8083
      }
    }

    # A surface that stays down is a platform that looks gone. Restart, unlike the batch
    # jobs where a failure is a verdict about the run.
    restart {
      attempts = 3
      interval = "5m"
      delay    = "15s"
      mode     = "delay"
    }

    task "server" {
      driver = "docker"

      # The attestation, and the only thing this workload is given. Its own role name —
      # a role bound to a different job id is a service that starts and authenticates as
      # nothing, which the API paid for once already.
      identity {
        name        = "vault"
        aud         = ["vault.io"]
        env         = true
        file        = true
        ttl         = "1h"
        change_mode = "restart"
      }

      config {
        image      = "ghcr.io/astral-sh/uv:python3.12-bookworm-slim"
        entrypoint = ["/bin/sh", "-c"]

        # BRIDGE MODE, AND IT IS BORN THIS WAY RATHER THAN CONVERTED.
        #
        # Measured 2026-07-31 with the API running and its own log confirming it was
        # listening: `200` from inside the Docker VM's namespace, nothing from macOS.
        # `network_mode = "host"` on Docker Desktop is the LINUX VM's namespace, and a
        # port block declared beside it is inert — every host-mode allocation shows an
        # empty Ports column while bridge-mode ones publish to `127.0.0.1`.
        #
        # A client on the developer's machine is the point of this surface (FR-014), so it
        # cannot live in host mode. Host mode is not decorative in the jobs that use it —
        # they reach the scheduler and the trust store at addresses that differ between the
        # VM and macOS — which is why this is a NEW job in bridge mode rather than a
        # conversion of one that works.
        ports = ["protocol"]

        # Read-only. The service reads code; it has no business writing to a developer's
        # tree, and on Linux root in a container is root on the host.
        mount {
          type     = "bind"
          source   = var.repo
          target   = "/src"
          readonly = true
        }

        mount {
          type     = "bind"
          source   = "${var.repo}/.enclave/uv-cache"
          target   = "/uv-cache"
          readonly = false
        }

        args = [
          "set -e; mkdir -p /repo; cp -a /src/pyproject.toml /src/uv.lock /src/README.md /src/src /repo/; cd /repo; export PYTHONPYCACHEPREFIX=/tmp/pycache; uv run --extra adapters --extra surfaces python -m surfaces.mcp.served"
        ]
      }

      env {
        VAULT_ADDR   = var.vault_addr
        VAULT_CACERT = var.vault_cacert
        NOMAD_ADDR   = var.nomad_addr

        HARNESS_DB_HOST = var.db_host

        OIDC_ISSUER       = var.oidc_issuer
        OIDC_JWKS_URI     = var.oidc_jwks_uri
        OIDC_AUDIENCE     = var.oidc_audience
        OIDC_TENANT_CLAIM = var.oidc_tenant_claim

        AUTHORITY_CONTROLLED_PATH = var.authority_controlled_path

        MCP_SURFACE_HOST = "0.0.0.0"
        MCP_SURFACE_PORT = var.surface_port

        UV_PROJECT_ENVIRONMENT = "/tmp/venv"
        UV_CACHE_DIR           = "/uv-cache"
        UV_LINK_MODE           = "copy"
      }

      resources {
        cores  = 1
        memory = 512
      }
    }
  }
}
