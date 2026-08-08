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

variable "default_tenant" {
  type        = string
  description = "The tenant every record written by this surface is filed under. Required: `resolve_tenant` refuses rather than inventing one, because a default tenant chosen by accident is still a tenant."
}

variable "audit_egress_host" {
  type    = string
  default = "127.0.0.1"
}

variable "audit_egress_port" {
  type    = string
  default = "5433"
}

variable "audit_egress_dbname" {
  type    = string
  default = "collector"
}

variable "vault_addr" {
  type        = string
  default     = "https://127.0.0.1:8200"
  description = "Where the trust store answers. HTTPS once bring-up has switched the listener."
}

variable "nomad_addr" {
  description = <<-DESC
    Where the sweeper reaches the scheduler to dispatch a resume.

    `host.docker.internal` rather than `127.0.0.1`, because this service runs inside an
    allocation and the scheduler does not. A deployment whose scheduler is reachable on the
    container's own loopback should override this; the default is the dev enclave's shape.
  DESC
  default     = "http://host.docker.internal:4646"
}

variable "vault_cacert" {
  type    = string
  default = "/src/.enclave/ca.pem"
  description = <<-DESC
    Control-plane CA, as seen INSIDE the container.

    `/src`, not `/repo`, unlike the batch jobs: this task mounts the tree read-only at
    `/src` and runs from a copy at `/repo`. The CA is read from the mount rather than the
    copy deliberately — it is the one file that can change under a running service, and
    reading it live means a reissued CA is picked up without the copy going stale.
  DESC
}

variable "repo" {
  type        = string
  description = "Working tree to mount, as for the conformance and agent-run jobs."
}

variable "sweep_interval_seconds" {
  type        = string
  default     = "5"
  description = <<-DESC
    How often the supervisory loop sweeps for suspended runs and dependency health.

    Five seconds in the enclave, thirty in the code's own default, and the difference is
    deliberate. The durability rows wait for a REAL sweeper pass — that is the assertion, and
    ADR-0049's whole claim that consent to start a run is consent to finish it rests on
    nobody pressing anything. What those rows do not assert is the cadence.

    Measured 2026-07-31: one row spent 184 seconds waiting for passes at the thirty-second
    default, which was 26% of the entire enclave lane spent idle. The row still waits for a
    genuine pass; it waits less long for one. A production deployment sets whatever its
    operators choose and the code default is unchanged.
  DESC
}

job "mcp" {
  # 017's deployment lane. Every job definition must be a declared subject or an
  # explicitly excluded one — coverage that a process opts into is fail-open, and the
  # process nobody remembered to enrol is exactly the one nobody remembered to cover.
  meta {
    harness_surface     = "true"
    harness_shape       = "served"
    harness_covered_by  = "tests/conformance/evidence/test_the_service_ships.py"
    harness_lane_starts = "false"
  }

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
        image        = "ghcr.io/astral-sh/uv:python3.12-bookworm-slim"
        entrypoint   = ["/bin/sh", "-c"]
        network_mode = "host"

        # Read-only, unlike every batch job here, and the difference is not caution.
        #
        # This is the first workload that starts at BRING-UP rather than when a developer
        # runs something. Everything before it built the project on the host first, so the
        # editable-install artefacts under `src/` already existed and were owned by
        # whoever was working. This job gets there first, as root, and on Linux root in a
        # container is root on the host — so `src/harness.egg-info` becomes root-owned and
        # the next host build fails with "Cannot update time stamp of directory", which
        # names a directory and not the container that created it.
        #
        # Read-only makes that structurally impossible rather than ordering-dependent. The
        # service reads code; it has no business writing to a developer's tree.
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

        # Copied out of the read-only mount, because the build needs somewhere to write.
        # A service is a fine place for a snapshot: it runs the code it started with, and
        # `change_mode = restart` above is what makes it pick up anything new.
        #
        # Four paths rather than the whole tree: the manifests, the sources, and the README
        # the build backend resolves `readme = "README.md"` against. Copying everything
        # would drag a 164 MB host virtualenv and the git history into a container that
        # uses neither.
        args = [
          "set -e; mkdir -p /repo; cp -a /src/pyproject.toml /src/uv.lock /src/README.md /src/src /repo/; cd /repo; export PYTHONPYCACHEPREFIX=/tmp/pycache; uv run --extra adapters --extra surfaces python -m surfaces.mcp.server"
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
        MCP_INTERVAL_SECONDS = var.sweep_interval_seconds

        VAULT_ADDR   = var.vault_addr
        # WHERE THE SCHEDULER IS, from in here. Not `127.0.0.1`, which is what the dispatcher
        # defaults to and what a host process would want: this task runs inside an allocation,
        # and on the dev substrate its loopback is the Docker VM's. Vault and Postgres answer
        # there because they are containers in that VM; the scheduler runs natively on the host
        # and does not.
        #
        # Without this the sweeper's resume dispatch fails `Connection refused` on every pass —
        # which is what it did from 009 until 014, unnoticed, because nothing had ever written
        # a suspended-run index row for it to act on.
        NOMAD_ADDR   = var.nomad_addr
        VAULT_CACERT = var.vault_cacert

        # Outside the mounted tree, so running the service does not rebuild the
        # developer's virtualenv against the container's interpreter and back again.
        UV_PROJECT_ENVIRONMENT = "/tmp/venv"

        # WHERE the second copy is (015). Coordinates only, and deliberately here rather
        # than in Vault: an address is not a secret, and jobspec metadata is readable by
        # anyone with scheduler access. The CREDENTIAL never travels this way — it carries
        # SELECT on the whole evidence copy, so it comes from `database/static-creds/`
        # under this allocation's own attested identity, rotated by Vault on a period.
        #
        # Their absence is how an estate says it has no second copy: no coordinates, no
        # destination, posture ABSENT — stated rather than defaulted.
        AUDIT_EGRESS_HOST   = var.audit_egress_host
        AUDIT_EGRESS_PORT   = var.audit_egress_port
        AUDIT_EGRESS_DBNAME = var.audit_egress_dbname

        # Populated by `enclave-up`, shared by every allocation.
        UV_CACHE_DIR = "/uv-cache"
        # Cache and venv sit on different filesystems, so hardlinking is unavailable
        # and copying is the fallback uv would take anyway. Declared, so the warning
        # stays out of the logs where it reads like a fault.
        UV_LINK_MODE = "copy"
      }

      # Cores, not MHz. This node fingerprints its CPU total as a couple of dozen MHz, so
      # the default MHz-based reservation exceeds the whole node and the allocation sits
      # queued with "Resources exhausted" — a placement failure that looks nothing like a
      # resource declaration problem. 008 paid for this at T030.
      # `cpu`, not `cores`, and this service is the clearest case for it in the tree.
      #
      # It is a supervisory loop: it wakes, runs six short passes, and sleeps thirty
      # seconds. It held an exclusive core for the 0.1% of the time it is awake, and on a
      # 4-core CI runner that core was the difference between the fencing row placing its
      # two concurrent allocations and not placing them.
      #
      # The enclave was sized to consume exactly 100% of such a runner in two separate
      # phases — postgres + mcp + conformance during the in-allocation lane, postgres + mcp
      # + two agent-runs during the host lane, both landing on 9200 of 9200 MHz. Zero
      # headroom is not a budget, it is a coincidence that holds until anything is added,
      # and 015 added four megahertz.
      #
      # A small `cpu` is a scheduling WEIGHT, not a cap — Nomad only enforces a hard limit
      # when asked to — so this loop still gets what it needs on an idle node and yields
      # first under contention, which is the correct priority for a supervisor next to the
      # work it supervises. The value is small enough to fit the bogus ~24 MHz total that
      # Apple Silicon fingerprints locally, which is what keeps `cores` everywhere else.
      resources {
        cpu    = 4
        memory = 512
      }
    }
  }
}
