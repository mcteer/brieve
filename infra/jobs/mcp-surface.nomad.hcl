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

variable "default_tenant" {
  type        = string
  description = "The tenant every record written by this surface is filed under. Required: `resolve_tenant` refuses rather than inventing one, because a default tenant chosen by accident is still a tenant."
}

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

variable "nomad_oidc_issuer" {
  type        = string
  default     = "http://127.0.0.1:4646"
  description = <<-DESC
    The issuer string Nomad stamps into a workload identity token, which is what the surface's
    workload verifier matches on.

    **Not the address this allocation dials.** It is whatever the scheduler was configured to
    claim (`server { oidc_issuer }` in `infra/nomad/client.hcl`), and a token's issuer is a
    name rather than a route. `nomad_addr` is the route; these are separate on purpose.
  DESC
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

# Which model `ask` may call, as a Qualified-Matrix cell identifier
# (`anthropic/claude-opus@5`). Empty means no model is configured and every ask answers 503,
# which is what a deployment that has not chosen one actually has.
#
# **Not a credential and not a permission**, and the three-way split is the whole design: this
# says what the surface is WIRED to call, the ask binding says whether it MAY, and the trust
# store says whether the platform holds the authority to. An operator who sets this without
# authoring a binding is told about the binding, because governance is checked first.
variable "ask_model" {
  type    = string
  default = ""
}

variable "relevance_model" {
  type = string
  # 043. WHICH model the surface may build a relevance judge for. Never equal to `ask_model`:
  # ADR-0067 forbids a model judging its own output, and the surface refuses
  # `self_judged_relevance` at resolution if a binding pairs them. Empty means no judge can be
  # built and every ask refuses `relevance_unbound`, honestly.
  default = ""
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
        labels = {
          "com.docker.compose.project" = "brieve-local"
          "com.docker.compose.service"  = "mcp-surface"
        }

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
          # Same watchdog as the API, for the same wedge and the same reason — this surface
          # holds an identical hour-long identity, so it wedges identically. See
          # `infra/bin/identity-watchdog`.
          "set -e; mkdir -p /repo; cp -a /src/pyproject.toml /src/uv.lock /src/README.md /src/src /repo/; cp -a /src/corpus /repo/ 2>/dev/null || true; cd /repo; export PYTHONPYCACHEPREFIX=/tmp/pycache; sh /src/infra/bin/identity-watchdog /secrets/nomad_vault.jwt 60 surfaces.mcp.served & uv run --extra adapters --extra surfaces python -m surfaces.mcp.served"
        ]
      }

      env {
        # THE TENANT EVERY RECORD IS FILED UNDER, and it reached no jobspec until 045's
        # endorsed content made the omission visible.
        #
        # `.env` has set this since the estate existed and nothing passed it through, so every
        # surface read an empty string. It was invisible because `resolve_tenant` is normally
        # reached WITH a subject claim — the env is the fallback for paths that have no surface
        # — and because all three surfaces were empty in the same way, so they agreed.
        #
        # Accidental agreement, and the failure it hides is silent: set it on one surface and
        # not another, and the drift probe queries for an adopted version under `tenant-local`,
        # finds none, and reports permanent drift on every endorsed source while the console
        # writes under "".
        HARNESS_DEFAULT_TENANT = var.default_tenant
        VAULT_ADDR   = var.vault_addr
        VAULT_CACERT = var.vault_cacert
        NOMAD_ADDR   = var.nomad_addr

        HARNESS_DB_HOST = var.db_host

        OIDC_ISSUER       = var.oidc_issuer
        OIDC_JWKS_URI     = var.oidc_jwks_uri

        # THE WORKLOAD VERIFIER (054, T046b). `served.py` has built
        # `verifier_for(SubjectKind.WORKLOAD, …)` from these two since 019 and nothing has
        # ever set them here, so the surface has only ever admitted people. 054 needs a
        # dispatched run to reach it, which is a workload.
        #
        # **The two values are deliberately different, and that is the point.** The ISSUER is
        # the string Nomad stamps into the token — loopback, because that is what the
        # scheduler was configured to claim. The JWKS URI is where THIS allocation fetches the
        # keys, and from in here the scheduler is not on loopback: it runs natively on the
        # host while this runs in the Docker VM. Collapsing them into one variable is the
        # mistake 014 paid for with the sweeper's dispatcher.
        # 054: this allocation logs in to Vault as ITSELF. The handlers are shared with the
        # dispatched run, and each side must present its own role — that is what makes the
        # measurement's writes land where the grant is (`scratch-sweep`, held here) rather
        # than where it no longer exists (`scratch-policy-check`, removed from runs).
        HARNESS_VAULT_ROLE = "mcp-surface"

        OIDC_WORKLOAD_ISSUER   = var.nomad_oidc_issuer
        OIDC_WORKLOAD_JWKS_URI = "${var.nomad_addr}/.well-known/jwks.json"
        OIDC_AUDIENCE     = var.oidc_audience
        OIDC_TENANT_CLAIM = var.oidc_tenant_claim

        AUTHORITY_CONTROLLED_PATH = var.authority_controlled_path

        # 027. The credential itself is NOT here and must never be: it is read from the trust
        # store per ask under this surface's own attested identity. What a jobspec may carry is
        # which model to call, which is configuration rather than authority — and
        # `tests/conformance/identity/test_posture_matches_constitution.py` fails this file if a
        # vendor key ever appears beside it.
        ASK_MODEL       = var.ask_model
        RELEVANCE_MODEL = var.relevance_model

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
