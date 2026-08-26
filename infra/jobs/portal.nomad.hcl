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
  description = <<-DESC
    Where the northbound API answers, AS SEEN FROM THIS CONTAINER.

    Not loopback any more. This task runs in bridge mode (see the config block below), so
    `127.0.0.1` is the portal's own container and reaches nothing.

    **And it is not `host.docker.internal` either**, which is the obvious wrong guess. Measured
    from inside this container: that name resolves to Docker Desktop's macOS-facing address and
    routes OUT to the developer's machine, where the API — still in host mode — publishes
    nothing. The API listens in the Linux VM's host namespace, reachable from a bridge
    container only at that bridge's own gateway, which `portal-up` derives.

    This is the same distinction 014 paid for in the sweeper's dispatcher: an address correct
    for a host process and wrong for an allocation, failing with `Connection refused` where
    nobody was watching. The difference here is that the failure is loud — the portal's first
    page load reports it.
  DESC
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

job "portal" {
  # 017's deployment lane. Every job definition must be a declared subject or an
  # explicitly excluded one — coverage that a process opts into is fail-open, and the
  # process nobody remembered to enrol is exactly the one nobody remembered to cover.
  meta {
    harness_surface     = "true"
    harness_shape       = "served"
    harness_covered_by  = "tests/conformance/deployment/test_the_portal_read_its_configuration.py"
    harness_lane_starts = "true"
    harness_started_by  = var.harness_started_by
  }

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
        labels = {
          "com.docker.compose.project" = "brieve-local"
          "com.docker.compose.service"  = "portal"
        }

        image      = "ghcr.io/astral-sh/uv:python3.12-bookworm-slim"
        entrypoint = ["/bin/sh", "-c"]

        # BRIDGE MODE, AND THIS IS THE WHOLE FIX. It said `network_mode = "host"`, and the
        # port block above was therefore inert: host mode shares the Docker VM's network
        # namespace and publishes nothing, so `docker ps` showed an empty Ports column and
        # nothing on the developer's machine could reach 8082 — while `portal-up` ended by
        # telling them to open it in a browser.
        #
        # Measured 2026-07-31 with the portal running and answering: `200` from inside the
        # VM's namespace, no answer from macOS. `docker inspect` states it in one line —
        # `host  ports=map[]` here against `bridge  ports=map[5432/tcp:[{127.0.0.1 5432}]]`
        # for the database, which the host lanes reach from macOS on every run.
        #
        # **A browser-facing surface is the one thing that cannot live in host mode**, because
        # the browser is the one client that is never inside the VM. `postgres.nomad.hcl` had
        # the answer the whole time; this is its port block, copied.
        ports = ["http"]

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
        # Bump when the served templates/CSS must not be the previous allocation's copy.
        PORTAL_UI_EPOCH         = "20260826v"

        # TLS. The paths are as seen INSIDE this container — `/src` is the working tree,
        # bind-mounted read-only above, and `.enclave/` is where bring-up materialises what
        # the control plane issued. Both files are gitignored.
        PORTAL_TLS_CERT = "/src/.enclave/portal.crt"
        PORTAL_TLS_KEY  = "/src/.enclave/portal.key"

        # The session cookie is ALWAYS Secure and always `__Host-` prefixed; there is no
        # setting for it, and `session.cookie_attributes` explains at length why the flag
        # must not come back.
        #
        # **What used to be written here was wrong.** It said dev works over plain HTTP
        # because browsers treat loopback as a trustworthy origin. Chromium and Firefox do;
        # Safari does not, and wants a real https scheme. The accessibility lane drives
        # Chromium, so the claim was only ever checked where it holds — and in Safari the
        # callback succeeded, the cookie was discarded, and the portal rendered its own
        # sign-in page forever.
        #
        # So dev serves TLS too, with a certificate the control plane's own CA issued. That
        # is not "deferring the deployment posture" — it IS the posture, one enclave early.

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
