# SPDX-License-Identifier: Apache-2.0
#
# The MCP service — the first deliberately PERSISTENT component in this platform.
#
# Everything else here is a batch job that ends when its work ends, and ADR-0049 makes
# that ending part of the guarantee: a suspended run is a record, not a process holding a
# slot. This service is the deliberate opposite, and it exists because two mechanisms in
# that same ADR need something that outlives a run — the dependency health checker, which
# must answer on demand rather than at the next tick, and the sweeper, which resumes runs
# when a dependency recovers.
#
# The cost of that asymmetry, stated rather than implied: a persistent service holds an
# attested identity for as long as it runs, which is the least ephemeral thing in this
# platform. It is mitigated below rather than eliminated — a TTL with re-issue, and no
# product credential of any kind. This service starts runs and reads health; it does not
# act on the products agents operate, so there is nothing for it to hold.
#
# READ THIS JOBSPEC FOR WHAT IS ABSENT: no token, no password, no DSN, no mounted secret.

variable "vault_addr" {
  type        = string
  default     = "https://127.0.0.1:8200"
  description = "Where the trust store answers. HTTPS once bring-up has switched the listener."
}

variable "vault_cacert" {
  type        = string
  default     = "/repo/.enclave/ca.pem"
  description = "Control-plane CA, as seen INSIDE the container — the repo is mounted at /repo."
}

variable "repo" {
  type        = string
  description = "Working tree to mount, as for the conformance and agent-run jobs."
}

job "mcp" {
  # `service`, not `batch`. The only one in this tree.
  type = "service"

  group "mcp" {
    count = 1

    # Restart on failure, unlike every batch job here where a failure is a verdict. A
    # health checker that stays down stops being a health checker, and the platform would
    # then believe whatever it last recorded until staleness caught up — which is why the
    # store treats a stale record as unknown rather than trusting it.
    restart {
      attempts = 3
      interval = "5m"
      delay    = "15s"
      mode     = "delay"
    }

    task "server" {
      driver = "docker"

      # The attestation, and the only thing this workload is given.
      identity {
        name = "vault"
        aud  = ["vault.io"]
        env  = true
        file = true

        # A persistent service is a persistent identity, which is the closest thing to a
        # standing credential in this platform. The TTL is what keeps it from being one:
        # the identity is re-issued rather than held, and `change_mode = restart` makes
        # the service pick up the new one instead of running on a stale token — which
        # fails as an authentication error and reads as a Vault problem.
        ttl         = "1h"
        change_mode = "restart"
      }

      config {
        image        = "python:3.12-slim"
        entrypoint   = ["/bin/sh", "-c"]
        network_mode = "host"

        mount {
          type     = "bind"
          source   = var.repo
          target   = "/repo"
          readonly = false
        }

        args = [
          "set -e; cd /repo; export PYTHONPYCACHEPREFIX=/tmp/pycache; pip install --quiet --disable-pip-version-check uv; uv run --extra adapters --extra surfaces python -m surfaces.mcp.server"
        ]
      }

      env {
        VAULT_ADDR   = var.vault_addr
        VAULT_CACERT = var.vault_cacert

        # Outside the mounted tree, so running the service does not rebuild the
        # developer's virtualenv against the container's interpreter and back again.
        UV_PROJECT_ENVIRONMENT = "/tmp/venv"
      }

      # Cores, not MHz. This node fingerprints its CPU total as a couple of dozen MHz, so
      # the default MHz-based reservation exceeds the whole node and the allocation sits
      # queued with "Resources exhausted" — a placement failure that looks nothing like a
      # resource declaration problem. 008 paid for this at T030.
      resources {
        cores  = 1
        memory = 512
      }
    }
  }
}
