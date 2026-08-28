# SPDX-License-Identifier: Apache-2.0
#
# A RUN-SHAPED IDENTITY A CONFORMANCE ROW CAN BORROW (054, T011a).
#
# **Why this job has to exist at all.** 054's rows must attempt a real break-in under a real
# run's authority — the defect was demonstrated that way and ADR-0047 says the fix has to be
# demonstrated on the same terms. Three cheaper routes were tried against the live enclave and
# all three are closed (054 research R7):
#
#   1. `auth/token/create` with the run's policy names — 018's trick — produces a token with NO
#      identity entity. The grant templates on the entity, so every attempt is refused and the
#      suite goes green while asserting nothing. Worse than a missing row.
#   2. Reading a dispatched allocation's JWT is refused by Nomad: "Reading secret file
#      prohibited". That is the scheduler behaving correctly and is not to be worked around.
#   3. A job already matching the `agent-run` role — there is none, because
#      `agent_run_job_id_patterns` is listed explicitly rather than globbed, deliberately.
#
# **So the enclave is given one, and the cost is stated rather than hidden.** This job id is
# admitted to the `agent-run` role by an ENVIRONMENT-LEVEL pattern, set in dev and conformance
# and absent from the module default. Production's bound claims are untouched. A test-only job
# id is admissible only where the enclave is itself a test enclave.
#
# **It does nothing.** No entrypoint, no repository access beyond the CA, no network calls of
# its own. It sleeps holding an attested identity, so a row can exec in, log in as the run
# would, and make the attempts the contract requires. The credential never leaves the
# allocation: the row runs its attempt INSIDE, and reads only the verdicts back.
job "harness-run-probe" {
  # 017's deployment lane. Every job definition must be a declared subject or an explicitly
  # excluded one — coverage a process opts into is fail-open.
  meta {
    harness_surface     = "true"
    harness_shape       = "standing"
    harness_covered_by  = "tests/conformance/authority/test_run_scoped_write.py"
    harness_lane_starts = "false"
  }

  type        = "service"
  datacenters = ["dc1"]

  group "probe" {
    count = 1

    # A failing probe is a failing probe; retrying would hide a broken identity behind a
    # second attempt that happened to work.
    restart {
      attempts = 0
      mode     = "fail"
    }

    task "idle" {
      driver = "docker"

      # The attestation, and the whole point of the job. `aud` must match the role's
      # `bound_audiences` and the job id must match its `bound_claims`, or any workload could
      # assume this role and the identity check would be decorative.
      identity {
        name        = "vault"
        aud         = ["vault.io"]
        env         = true
        file        = true
        ttl         = "1h"
        change_mode = "restart"
      }

      # The surface identity a real run now carries (054, T046a). Mirrored here because the
      # probe's whole purpose is to be indistinguishable from a run to anything checking
      # identity — a probe missing an identity the runs have would let a row pass against a
      # shape production does not have.
      identity {
        name        = "mcp"
        aud         = ["brieve.mcp"]
        env         = false
        file        = true
        ttl         = "10m"
        change_mode = "noop"
      }

      config {
        labels = {
          "com.docker.compose.project" = "brieve-local"
          "com.docker.compose.service" = "run-probe"
        }

        image        = "ghcr.io/astral-sh/uv:python3.12-bookworm-slim"
        entrypoint   = ["/bin/sh", "-c"]
        network_mode = "host"

        # The CA only. This job reads no source and runs none.
        mount {
          type     = "bind"
          source   = var.repo
          target   = "/repo"
          readonly = true
        }

        # Bounded rather than endless: a probe nobody stopped is a standing identity, which is
        # the shape this platform refuses everywhere else. `make dev-up` places a fresh one.
        args = ["sleep 7200"]
      }

      resources {
        cpu    = 100
        memory = 128
      }
    }
  }
}

variable "repo" {
  type        = string
  description = "Working tree to mount read-only, for the control-plane CA. As the other jobs."
}
