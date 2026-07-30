# SPDX-License-Identifier: Apache-2.0
#
# The conformance suite as a scheduled workload — the gap 005 left open.
#
# Until this existed, the durability rows ran on the host against a development token, so
# the attestation path was proven BESIDE the tests rather than BY them. That is a weaker
# claim than the conformance contract implies, and it was the only place a static token
# remained anywhere in the tree.
#
# READ THIS JOBSPEC FOR WHAT IS ABSENT: no token, no password, no DSN, no mounted secret.
# The only thing this job is given is proof of who it is.

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
  description = "Working tree to mount. Mounted rather than baked into an image: an image build per run would make the durability rows something people avoid running, and they are already the only place those guarantees are checked."
}

job "conformance" {
  type = "batch"

  group "durability" {
    # A failing suite is a failing suite. Retrying would turn a red gate amber.
    reschedule {
      attempts  = 0
      unlimited = false
    }

    restart {
      attempts = 0
    }

    task "pytest" {
      driver = "docker"

      # The attestation. `aud` must match the Vault role's bound_audiences and the job id
      # must match its bound_claims — otherwise any workload could assume this role and
      # the identity check would be decorative.
      identity {
        name = "vault"
        aud  = ["vault.io"]
        env  = true
        file = true
        # An identity without an expiry is a standing credential wearing a different
        # hat. The suite is a batch job; an hour is generous for it.
        ttl = "1h"
        # Without this the task keeps a stale identity across a re-issue, which fails as
        # an authentication error and reads as a Vault problem.
        change_mode = "restart"
      }

      config {
        image      = "ghcr.io/astral-sh/uv:python3.12-bookworm-slim"
        entrypoint = ["/bin/sh", "-c"]
        network_mode = "host"

        mount {
          type     = "bind"
          source   = var.repo
          target   = "/repo"
          readonly = false
        }

        # THE PACKAGE CACHE, SHARED ACROSS ALLOCATIONS.
        #
        # Every allocation builds its own virtualenv, and until this mount existed it built
        # it from the public package index — roughly seventy wheels over the network, per
        # run. That is the single largest source of red gates this tree has: a row that
        # drives the scheduler cannot start until PyPI answers, and when PyPI times out the
        # allocation dies before reaching the entrypoint. 014's gate run lost two rows that
        # way, and an earlier one spent ten minutes reporting a read timeout as a failure of
        # the revival cap.
        #
        # Cached rather than baked into an image, which keeps the reason the repo is MOUNTED
        # rather than baked (see `var.repo` on the conformance job): an image build per
        # change would make these rows something people avoid running. The cache is the
        # middle ground — the tree stays live, the downloads happen once per machine.
        #
        # Measured: 90s+ of downloads becomes 72 packages installed in ~400ms, and the
        # bootstrap completes with the network disconnected entirely.
        mount {
          type     = "bind"
          source   = "${var.repo}/.enclave/uv-cache"
          target   = "/uv-cache"
          readonly = false
        }

        # No shell parameter expansion here. Nomad interpolates ${...} in args before
        # the shell ever sees them, so a default like ${VAR:-x} fails to parse with an
        # error about interpolation rather than about the script. VAULT_ADDR comes from
        # the env block below instead.
        #
        # No VAULT_TOKEN is set, deliberately. The suite authenticates as this workload
        # or it does not run.
        args = [
          "set -e; cd /repo; export PYTHONPYCACHEPREFIX=/tmp/pycache; uv run --extra adapters --extra surfaces pytest tests/conformance/durability tests/conformance/api tests/conformance/identity -m \"not host_enclave\" -q"
        ]
      }

      env {
        # Must follow the listener. Hardcoding http here is how a working TLS enclave
        # produces "could not obtain a database credential ... HTTPError" — which names
        # the credential path and not the scheme that actually broke.
        VAULT_ADDR = var.vault_addr

        # The CA lives in the mounted working tree, so the path is a container path.
        # Without it every request fails certificate verification, which surfaces as the
        # same credential error.
        VAULT_CACERT = var.vault_cacert

        # Build the virtualenv OUTSIDE the mounted tree.
        #
        # The mount is writable, so `uv run` in /repo resolved .venv to the DEVELOPER'S
        # virtualenv and rebuilt it against the container's interpreter — after which the
        # host's `uv run` found ".venv/bin/python3 -> python" dangling and rebuilt it
        # back. Every alternation between a local command and this workload paid for a
        # full reinstall, which is what pushed a cold run past the wait bound above and
        # made the gate report red on rows that passed.
        #
        # Running the merge gate should not damage the environment of the person running
        # it. A container path keeps the two apart.
        UV_PROJECT_ENVIRONMENT = "/tmp/venv"

        # Where the wheels come from. Populated by `enclave-up` and shared by every
        # allocation, so a run reaches for the network only on a genuine cache miss.
        UV_CACHE_DIR = "/uv-cache"
        # The cache and the venv are on different filesystems, so uv cannot hardlink
        # between them. Copying is what it falls back to anyway; saying so keeps a
        # warning about degraded performance out of every allocation's logs, where it
        # reads like a fault and is not one.
        UV_LINK_MODE = "copy"
      }

      resources {
        cores  = 2
        memory = 1024
      }
    }
  }
}
