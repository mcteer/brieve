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
      }

      env {
        POSTGRES_USER     = "brieve"
        POSTGRES_DB       = "brieve"
        # Dev bootstrap only. The durability feature replaces this with a
        # credential the workload obtains from Vault under its own identity.
        POSTGRES_PASSWORD = "dev-only-not-a-secret"
      }

      resources {
        cores  = 1
        memory = 512
      }
    }
  }
}
