# SPDX-License-Identifier: Apache-2.0
#
# Postgres runs UNDER Nomad — unlike Vault. It is an ordinary workload with no
# role in establishing trust, so scheduling it in the substrate creates no
# circularity and no containment concern (ADR-0048).
#
# NOTE: `cores` rather than `cpu`. Nomad's CPU fingerprint on Apple Silicon
# reports a total of ~24 MHz while correctly detecting the core count, so any
# MHz-based request above that is unschedulable. `cores` sidesteps the bad
# fingerprint and is portable.

# WHY THIS EXISTS: on Docker Linux a published port binds ONE interface, and this job's
# static port lands on `127.0.0.1` because `infra/nomad/client.hcl` advertises loopback
# (deliberately — WSL's `eth0` address changes on every restart). A container in BRIDGE
# mode resolves the host to the docker0 gateway, `172.17.0.1`, where nothing is listening,
# so it cannot reach the state store at all. `mcp-surface` is that caller, and bridge mode
# is not optional for it (FR-014).
#
# Docker Desktop hides this: `host.docker.internal` there reaches ports published on the
# developer's loopback. That is why the assumption written into `mcp-surface.nomad.hcl`'s
# `db_host` — "Postgres publishes 127.0.0.1:5432 … which from a bridge container is
# host.docker.internal" — holds on a Mac and fails on Docker Linux.
#
# In host mode Postgres binds `0.0.0.0:5432` in the host namespace, so BOTH `127.0.0.1`
# (host-mode callers, and `enclave-up`'s own readiness probe) and `172.17.0.1` (bridge
# callers) reach it. The `port "pg"` block below stays: it no longer publishes anything,
# but it still reserves 5432 for scheduling and still catches a port collision.
#
# Off by default, and it must stay off on Docker Desktop: `network_mode = "host"` there is
# the Linux VM's namespace, so the port would vanish from macOS and from any bridge
# container — the exact breakage this flag is meant to repair. Same substrate fact as
# `ENCLAVE_VAULT_HOST_NETWORK`, which is what `enclave-up` derives it from.
variable "host_network" {
  type        = bool
  default     = false
  description = "Run the state store in the host network namespace (Docker Linux / WSL2)."
}

job "postgres" {
  type = "service"

  group "db" {
    network {
      port "pg" { static = 5432 }
    }

    task "postgres" {
      driver = "docker"

      config {
        image = "postgres:17-alpine"
        ports = ["pg"]

        # `null`, not `"bridge"`, when off — the attribute goes unset and the driver's own
        # default applies, so a Mac sees byte-for-byte the behaviour it had before. Mirrors
        # `infra/modules/substrate-docker/main.tf:113`, which does this for the trust store.
        network_mode = var.host_network ? "host" : null

        labels = {
          "com.docker.compose.project" = "brieve-local"
          "com.docker.compose.service"  = "postgres"
        }

        # A Docker named volume rather than a Nomad host volume: it needs no
        # client configuration, so `nomad agent -dev` can use it unchanged. The
        # data outlives both the allocation and the Nomad agent, which is the
        # point — a checkpoint store that dies with the process is not durable.
        mount {
          type   = "volume"
          target = "/var/lib/postgresql/data"
          source = "brieve-dev-pgdata"
        }
      }

      env {
        POSTGRES_USER = "brieve"
        POSTGRES_DB   = "brieve"

        # BOOTSTRAP SCAFFOLDING — to be removed, not kept.
        #
        # This root account exists so Vault's database secrets engine has
        # something to connect as while it creates dynamic roles. The harness
        # never uses it: it authenticates to the control-plane Vault with its
        # Nomad workload identity and receives a short-lived, per-workload
        # credential minted on demand (FR-017a, Principle IV).
        #
        # Configuring that engine belongs to the deployment module tree. Until
        # it lands, this password is the only standing credential in the
        # enclave, and it is a placeholder rather than a design.
        POSTGRES_PASSWORD = "dev-only-not-a-secret"
      }

      resources {
        cores  = 1
        memory = 512
      }
    }
  }
}
