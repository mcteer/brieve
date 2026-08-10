# SPDX-License-Identifier: Apache-2.0
#
# The SECOND copy of the audit trail, and the whole of ADR-0055 turns on what is absent
# here rather than on what is present.
#
# **This store is NOT registered in the platform Vault's database secrets engine.** That
# absence is the feature. A destination whose credentials the platform's Vault mints is a
# destination the platform's administrators govern — and the threat this exists to detect
# is precisely an actor with that administrative reach. ADR-0055 forecloses the shortcut by
# name: "shipping to object storage the enclave's own workload role can write would be
# trivial to build, would look like a second copy, and would be worthless."
#
# So the platform reaches this store with a static, append-only credential the COLLECTOR
# administrator issued (`infra/collector/roles.sql`), holding INSERT and SELECT and nothing
# else. `enclave-up` plays the collector administrator in dev, which is a simulation of
# separate administration rather than the real thing — one operator wears both hats here,
# and `contracts/conformance-egress.md` says so under "what these rows do not prove".
# What IS real, and what the rows demonstrate, is the credential separation: the platform's
# own credential cannot alter what it has shipped.
#
# NOTE: `cpu`, NOT `cores` — and this is the one job in the tree where that is right.
#
# Every other job here uses `cores` because Nomad's CPU fingerprint on Apple Silicon reports
# ~24 MHz total while correctly detecting the core count, so an MHz-based request sized for a
# real machine is unschedulable locally. This job started that way too, and it broke CI.
#
# `cores` reserves cores EXCLUSIVELY. On a 4-core runner the budget is postgres(1) + mcp(1)
# + this(1) = 3, leaving one for a conformance job that asks for 2 — so the conformance job
# could not be placed and `nomad job run` exited 2 on every push to this branch, while every
# local run passed on a machine with eighteen cores. A second exclusive core is not something
# a second copy under a trickle of inserts has any claim to.
#
# The value is small enough to fit the bogus 24 MHz local total and irrelevant on a real one,
# which is the property that makes an MHz request workable HERE and nowhere else: this task
# is idle almost always, so it never needs a share worth reserving.

job "collector-postgres" {
  type = "service"

  group "db" {
    network {
      # A distinct static port. Same host, different store: the enclave is a single
      # machine, so topological separation is not available here and is not what
      # ADR-0055 asks for — "the trust boundary is administrative, not topological".
      #
      # `to = 5432` because Postgres listens on its default inside the container and only
      # the OUTSIDE of the mapping needs to differ from the platform's store. Without it
      # the mapping is 5433->5433 and nothing is listening on the far side — a connection
      # refused that looks like a store which failed to start, on a container that is
      # running perfectly.
      port "pg" {
        static = 5433
        to     = 5432
      }
    }

    task "collector-postgres" {
      driver = "docker"

      config {
        image = "postgres:17-alpine"
        ports = ["pg"]

        labels = {
          "com.docker.compose.project" = "brieve-local"
          "com.docker.compose.service"  = "collector-postgres"
        }

        # Its OWN volume, deliberately not shared with the platform's store. A second copy
        # on the same volume would fail the same disk, which is the least interesting of
        # the failure modes but the easiest to overlook.
        mount {
          type   = "volume"
          target = "/var/lib/postgresql/data"
          source = "brieve-dev-collector-pgdata"
        }
      }

      env {
        POSTGRES_USER = "collector"
        POSTGRES_DB   = "collector"

        # The COLLECTOR ADMINISTRATOR's password, and the distinction from
        # `postgres.nomad.hcl`'s bootstrap account is the point of this whole feature.
        #
        # That one is scaffolding awaiting Vault's secrets engine. This one is never going
        # to be managed by the platform's Vault, because a credential the platform can mint
        # is a credential the platform's administrators control — and this account is the
        # one that CAN rewrite the second copy. It stays operator-held.
        #
        # In dev it is a placeholder. In a real deployment the collector administrator sets
        # it and the platform never learns it; the platform receives only the append-only
        # credential that `roles.sql` creates.
        POSTGRES_PASSWORD = "dev-only-collector-admin"
      }

      resources {
        cpu    = 4
        memory = 256
      }
    }
  }
}
