# SPDX-License-Identifier: Apache-2.0
#
# The conversational portal (ADR-0034) — a thin client of the API above.
#
# It holds NO credential of any kind: no client secret (it is a public OIDC client using
# PKCE), no Vault identity, no database access. It relays a person's own token to the API,
# which is why a run started here is indistinguishable from one started through the API —
# it is one.
#
# Note what this job does not have that every other service here does: an `identity`
# block. The portal has nothing to authenticate AS. That absence is the design.

variable "api_base_url" {
  type        = string
  description = "Where the northbound API answers. Loopback inside the enclave for dev."
}

variable "oidc_authorize_endpoint" {
  type        = string
  description = "Where a person is sent to sign in. Must be reachable from their BROWSER."
}

variable "oidc_token_endpoint" {
  type        = string
  description = "Where the portal redeems an authorization code. Server-side only."
}

variable "oidc_issuer" {
  type = string
}

variable "oidc_audience" {
  type        = string
  default     = ""
  description = <<-DESC
    Which API the access token is FOR, forwarded on the authorization request.

    Empty for the development provider, which does not use it. Required against a real
    one: Auth0 issues an opaque token rather than a JWT when no audience is asked for, and
    the API then refuses it as unverifiable — an error naming the token rather than the
    missing parameter.
  DESC
}

variable "portal_client_id" {
  type    = string
  default = "harness-portal"
  description = <<-DESC
    The public client identifier. Public: there is no secret to go with it.

    A confidential client would need one in this jobspec, which is the static credential
    Principle IV prohibits without exception. PKCE exists precisely so a client with no
    secret can still prove it is the party that requested the code it is redeeming.
  DESC
}

variable "portal_redirect_uri" {
  type        = string
  description = "Where the IdP returns the person. Must match what the IdP has registered."
}

variable "repo" {
  type = string
}

job "portal" {
  type = "service"

  group "portal" {
    count = 1

    network {
      port "http" {
        static = 8082
      }
    }

    restart {
      attempts = 3
      interval = "5m"
      delay    = "15s"
      mode     = "delay"
    }

    task "server" {
      driver = "docker"

      config {
        image        = "ghcr.io/astral-sh/uv:python3.12-bookworm-slim"
        entrypoint   = ["/bin/sh", "-c"]
        network_mode = "host"

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

        args = [
          "set -e; mkdir -p /repo; cp -a /src/pyproject.toml /src/uv.lock /src/README.md /src/src /repo/; cd /repo; export PYTHONPYCACHEPREFIX=/tmp/pycache; uv run --extra surfaces --extra portal python -m surfaces.portal.service"
        ]
      }

      env {
        API_BASE_URL            = var.api_base_url
        OIDC_ISSUER             = var.oidc_issuer
        OIDC_AUTHORIZE_ENDPOINT = var.oidc_authorize_endpoint
        OIDC_TOKEN_ENDPOINT     = var.oidc_token_endpoint
        OIDC_AUDIENCE           = var.oidc_audience
        PORTAL_CLIENT_ID        = var.portal_client_id
        PORTAL_REDIRECT_URI     = var.portal_redirect_uri
        PORTAL_BIND             = "0.0.0.0:8082"

        # The session cookie is ALWAYS Secure and always `__Host-` prefixed; there is no
        # setting for it. Dev works over plain HTTP because browsers treat loopback as a
        # trustworthy origin. A real deployment terminates TLS in front of this — that
        # posture is a deployment concern and is deliberately not solved here.

        UV_PROJECT_ENVIRONMENT = "/tmp/venv"

        # Populated by `enclave-up`, shared by every allocation.
        UV_CACHE_DIR = "/uv-cache"
        # Cache and venv sit on different filesystems, so hardlinking is unavailable
        # and copying is the fallback uv would take anyway. Declared, so the warning
        # stays out of the logs where it reads like a fault.
        UV_LINK_MODE = "copy"
      }

      resources {
        cores  = 1
        memory = 384
      }
    }
  }
}
