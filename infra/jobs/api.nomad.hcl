# SPDX-License-Identifier: Apache-2.0
#
# The northbound API — and this is its FIRST deployment.
#
# 008 built `create_app` and every feature since has exercised it: in tests, and mirrored
# inside the MCP transport's assembly. Nothing ever served it. Every operation row and
# every parity row has therefore been true about an app object rather than about a running
# service, which is not wrong but is narrower than it reads. 012 needs the API served
# because the portal is a thin client OVER it (ADR-0034), and a client cannot be over
# something that is not there.
#
# READ THIS JOBSPEC FOR WHAT IS ABSENT: no token, no password, no DSN, no mounted secret.
# The service presents its workload identity and receives what it is entitled to.

variable "default_tenant" {
  type        = string
  description = "The tenant every record written by this surface is filed under. Required: `resolve_tenant` refuses rather than inventing one, because a default tenant chosen by accident is still a tenant."
}

variable "vault_addr" {
  type        = string
  default     = "https://127.0.0.1:8200"
  description = "Where the trust store answers."
}

variable "vault_cacert" {
  type        = string
  default     = "/src/.enclave/ca.pem"
  description = "Control-plane CA as seen inside the container, read from the live mount."
}

variable "oidc_issuer" {
  type        = string
  description = <<-DESC
    The issuer this API verifies human tokens against.

    In dev this is the fake provider `make dev-up` runs — the customer's IdP is the one
    thing outside this platform's boundary, so it is the one thing doubled. In a real
    deployment it is the organization's own OIDC provider, and nothing else changes.
  DESC
}

variable "oidc_jwks_uri" {
  type        = string
  description = "Where the API fetches signing keys. Public material only."
}

variable "oidc_workload_issuer" {
  type        = string
  default     = ""
  description = <<-DESC
    Issuer whose tokens this surface accepts as MACHINE identities. Empty accepts none.

    Usually the same string as `oidc_issuer`: Auth0, Okta, Ping and Entra all serve
    `client_credentials` and `authorization_code` from one issuer. Named anyway rather
    than inferred, because "this surface accepts machine credentials" is a posture
    somebody decides. Left empty, a leaked client secret is refused rather than being a
    working operator login.
  DESC
}

variable "oidc_workload_jwks_uri" {
  type        = string
  default     = ""
  description = "JWKS for the workload issuer. Empty reuses `oidc_jwks_uri`, which is right when one issuer serves both."
}

# Which model `ask` may call, as a Qualified-Matrix cell identifier. Empty means no model is
# configured and every ask answers 503. Mirrors the served MCP surface's variable exactly —
# ADR-0033 is about what a deployment does, so the two assemblies take the same configuration or
# surface parity becomes a claim about a test fixture.
#
# **The credential is deliberately not here** and must never be: it is read from the trust store
# per ask under this surface's own attested identity, and the posture check fails this file if a
# vendor key ever appears beside it.
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

variable "propose_owned_repositories" {
  type        = string
  default     = ""
  description = <<-DESC
    047. Comma-separated owner/repo identifiers Propose may target. Empty refuses every
    repository (fail closed). Dev commonly sets mcteer/brieve-demo.
  DESC
}

variable "oidc_tenant_claim" {
  type        = string
  default     = "tenant"
  description = <<-DESC
    Which claim carries the tenant.

    Configuration rather than a constant because no provider emits a bare `tenant`, and
    Auth0, Okta and Ping all REFUSE to mint an un-namespaced custom claim — so a real
    deployment sends `https://example.com/tenant` and the default refuses every token it
    issues with `no_tenant`.
  DESC
}

variable "oidc_audience" {
  type        = string
  default     = "harness-api"
  description = "The audience this API accepts. A token for another service is refused."
}

variable "authority_controlled_path" {
  type        = string
  default     = "harness-authority/data/claim-mappings"
  description = "The Control-Group-gated path claim-mapping changes are written to."
}

variable "repo" {
  type        = string
  description = "Working tree to mount, as for the MCP service."
}

variable "harness_started_by" {
  type    = string
  default = ""
  description = <<-DESC
    Set by the deployment lane to claim ownership of a surface it started.

    Empty when a person runs `portal-up` — their surfaces carry no mark and the lane will
    never stop them. The value lives in the job's `Meta` rather than in the memory of
    whatever submitted it, so a LATER invocation can tell a leftover from someone's own
    work; an in-process record dies with the run and leaves reclamation choosing between
    stopping everything and stopping nothing (017, FR-007a).
  DESC
}

job "api" {
  # 017's deployment lane. Every job definition must be a declared subject or an
  # explicitly excluded one — coverage that a process opts into is fail-open, and the
  # process nobody remembered to enrol is exactly the one nobody remembered to cover.
  meta {
    harness_surface     = "true"
    harness_shape       = "served"
    harness_covered_by  = "tests/conformance/deployment/test_the_api_answers_as_itself.py"
    harness_lane_starts = "true"
    harness_started_by  = var.harness_started_by
  }

  type = "service"

  group "api" {
    count = 1

    network {
      port "http" {
        static = 8081
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

      identity {
        name = "vault"
        aud  = ["vault.io"]
        env  = true
        file = true

        # Same reasoning as the MCP service: a persistent identity is the closest thing to
        # a standing credential here, and the TTL with re-issue is what keeps it from
        # becoming one.
        ttl         = "1h"
        change_mode = "restart"
      }

      config {
        labels = {
          "com.docker.compose.project" = "brieve-local"
          "com.docker.compose.service"  = "api"
        }

        # **NOT `-slim`, and the difference is `git`** (045). This surface syncs a customer's
        # endorsed sources, which means cloning a repository, and the slim image carries no
        # git — so every Review failed at the click while the console rendered perfectly.
        #
        # The same publisher and the same Python, so this is a one-word change rather than a
        # new supply chain. A runtime `apt-get` was the obvious alternative and is refused for
        # the reason the authoring tier records: an unpinned network fetch at task start, on a
        # surface that then handles repository content.
        image        = "ghcr.io/astral-sh/uv:python3.12-bookworm"
        entrypoint   = ["/bin/sh", "-c"]
        network_mode = "host"

        # Read-only, and copied before install — 009's lesson. This service starts at
        # bring-up as root, and on Linux root in a container is root on the host, so a
        # writable mount leaves root-owned build artefacts in a developer's tree.
        mount {
          type     = "bind"
          source   = var.repo
          target   = "/src"
          readonly = true
        }

        # THE PACKAGE CACHE, SHARED ACROSS ALLOCATIONS. See `agent-run.nomad.hcl` for the
        # full reasoning: every allocation built its virtualenv from the public index, which
        # made the network a precondition for the service starting at all.
        #
        # Writable, unlike the source mount above — a cache nothing may write to is not a
        # cache. The source stays read-only because this task COPIES what it needs out of it
        # and must not be able to edit the tree it was given.
        mount {
          type     = "bind"
          source   = "${var.repo}/.enclave/uv-cache"
          target   = "/uv-cache"
          readonly = false
        }

        # 047 — Propose/Build clones the owned repository here before dispatching
        # authoring-tier. The path must be host-visible so Nomad can bind-mount the same
        # checkout into the analyzer (`PROPOSE_SUBJECT_HOST_ROOT` below).
        mount {
          type     = "bind"
          source   = "${var.repo}/.enclave/propose-subjects"
          target   = "/propose-subjects"
          readonly = false
        }

        args = [
          # The watchdog runs beside the service and restarts the task when the workload
          # identity on disk has expired — see `infra/bin/identity-watchdog` for what it is
          # repairing and why a restart is the whole repair. Started before the server so a
          # surface that comes up with an already-dead identity recovers too.
          "set -e; mkdir -p /repo; cp -a /src/pyproject.toml /src/uv.lock /src/README.md /src/src /repo/; cp -a /src/corpus /repo/ 2>/dev/null || true; cd /repo; export PYTHONPYCACHEPREFIX=/tmp/pycache; sh /src/infra/bin/identity-watchdog /secrets/nomad_vault.jwt 60 surfaces.api.service & uv run --extra adapters --extra surfaces python -m surfaces.api.service"
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

        OIDC_ISSUER            = var.oidc_issuer
        OIDC_JWKS_URI          = var.oidc_jwks_uri
        OIDC_AUDIENCE          = var.oidc_audience
        OIDC_TENANT_CLAIM      = var.oidc_tenant_claim
        OIDC_WORKLOAD_ISSUER   = var.oidc_workload_issuer
        OIDC_WORKLOAD_JWKS_URI = var.oidc_workload_jwks_uri

        API_BIND = "0.0.0.0:8081"

        # The Control-Group-gated path claim-mapping changes are written to (ADR-0016).
        # Named here rather than defaulted in code: a submitter pointed at an ungated path
        # would write changes that look approved.
        AUTHORITY_CONTROLLED_PATH = var.authority_controlled_path

        ASK_MODEL       = var.ask_model
        RELEVANCE_MODEL = var.relevance_model

        # 047. Fail closed when empty — see var.propose_owned_repositories.
        PROPOSE_OWNED_REPOSITORIES = var.propose_owned_repositories
        PROPOSE_ACQUIRE_ROOT       = "/propose-subjects"
        PROPOSE_SUBJECT_HOST_ROOT  = "${var.repo}/.enclave/propose-subjects"

        UV_PROJECT_ENVIRONMENT = "/tmp/venv"

        # Populated by `enclave-up`, shared by every allocation.
        UV_CACHE_DIR = "/uv-cache"
        # Cache and venv sit on different filesystems, so hardlinking is unavailable
        # and copying is the fallback uv would take anyway. Declared, so the warning
        # stays out of the logs where it reads like a fault.
        UV_LINK_MODE = "copy"
      }

      # Cores, not MHz — 008 paid for this at T030 and the failure looks like a placement
      # problem rather than a resource declaration one.
      resources {
        cores  = 1
        memory = 512
      }
    }
  }
}
