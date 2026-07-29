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

job "api" {
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
        image        = "python:3.12-slim"
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

        args = [
          "set -e; mkdir -p /repo; cp -a /src/pyproject.toml /src/uv.lock /src/README.md /src/src /repo/; cd /repo; export PYTHONPYCACHEPREFIX=/tmp/pycache; pip install --quiet --disable-pip-version-check uv; uv run --extra adapters --extra surfaces python -m surfaces.api.service"
        ]
      }

      env {
        VAULT_ADDR   = var.vault_addr
        VAULT_CACERT = var.vault_cacert

        OIDC_ISSUER   = var.oidc_issuer
        OIDC_JWKS_URI = var.oidc_jwks_uri
        OIDC_AUDIENCE = var.oidc_audience

        API_BIND = "0.0.0.0:8081"

        # The Control-Group-gated path claim-mapping changes are written to (ADR-0016).
        # Named here rather than defaulted in code: a submitter pointed at an ungated path
        # would write changes that look approved.
        AUTHORITY_CONTROLLED_PATH = var.authority_controlled_path

        UV_PROJECT_ENVIRONMENT = "/tmp/venv"
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
