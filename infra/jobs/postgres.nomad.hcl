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
