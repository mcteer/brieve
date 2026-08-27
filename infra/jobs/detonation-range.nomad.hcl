# SPDX-License-Identifier: Apache-2.0
#
# THE DETONATION RANGE (037, FR-012/FR-015).
#
# **Not the development identity stand-in.** ADR-0053 described the range as that fake, and
# 037's clarification refused it: the fake is test-only and guarded by a merge-blocking rule
# requiring every conformance row using it to declare which failure it injects. Reusing it
# would mean amending that guard so the fake acquires a production life — weakening a control
# to accommodate a convenience, which is what this repository refused when it declined psycopg
# rather than loosen the licence gate.
#
# So the range holds NO AUTHORITY SOURCE AT ALL. That is not a configuration choice to be
# relaxed later; it is the component's defining property. A range that could reach real
# authority is a detonation chamber with a door.
#
# The named trigger Principle VI requires for an operated component is in ADR-0053's Accepted
# form: stage 5 needs a place to execute a presumed-hostile candidate where it can do nothing,
# and a place is not a library.
job "detonation-range" {
  # 017's deployment lane. Every job definition must be a declared subject or an
  # explicitly excluded one — coverage a process opts into is fail-open, and the
  # process nobody remembered to enrol is exactly the one nobody remembered to cover.
  #
  # 037's detonation range. Dispatched per candidate — the lane does not stand it up,
  # and `test_detonation.py` is what drives and asserts it.
  meta {
    harness_surface     = "true"
    harness_shape       = "dispatched"
    harness_covered_by  = "tests/conformance/intake/test_detonation.py"
    harness_lane_starts = "false"
  }
  type        = "batch"
  datacenters = ["dc1"]

  parameterized {
    payload       = "required"
    meta_required = ["candidate_digest", "correlation_id", "role"]
  }

  group "range" {
    restart { attempts = 0 }

    network {
      # No host namespace, for the same reason as the analysis tier — and here with a second
      # reason: the specimen is presumed infected, and a presumed-infected workload on the
      # machine's own network is the thing a range exists to prevent.
      mode = "bridge"
    }

    # THE SPECIMEN. Executes the candidate. Presumed infected from the moment it starts.
    task "specimen" {
      driver = "docker"

      identity {
        name        = "vault"
        aud         = ["vault.io"]
        env         = true
        file        = true
        ttl         = "1h"
        change_mode = "restart"
      }

      config {
        labels = {
          "com.docker.compose.project" = "brieve-local"
          "com.docker.compose.service"  = "detonation-specimen"
        }

        image        = "ghcr.io/astral-sh/uv:python3.12-bookworm-slim"
        entrypoint   = ["/bin/sh", "-c"]
        network_mode = "bridge"
      }

      env {
        # No authority source. Not a fake one, not a scoped one — none. The estate this
        # candidate can reach is empty, and the canaries below are how an attempt to reach
        # past it becomes visible.
        HARNESS_AUTHORITY_SOURCE = ""
        HARNESS_RANGE_ROLE       = "specimen"
        # Canaries: planted material whose appearance anywhere outside this range is proof of
        # exfiltration. Seeded here so detection is mechanical rather than a reader noticing.
        HARNESS_CANARY_IDS = "canary-alpha,canary-beta"
      }

      resources {
        cpu    = 500
        memory = 512
      }
    }

    # THE OBSERVER. A SEPARATE TASK, therefore a separate workload identity, therefore a
    # separate attested principal. It reads the specimen's audit records and spans from
    # outside and never receives its output — the load-bearing separation, made structural by
    # being two tasks rather than one process with a discipline.
    task "observer" {
      driver = "docker"

      identity {
        name        = "vault"
        aud         = ["vault.io"]
        env         = true
        file        = true
        ttl         = "1h"
        change_mode = "restart"
      }

      config {
        labels = {
          "com.docker.compose.project" = "brieve-local"
          "com.docker.compose.service"  = "detonation-observer"
        }

        image        = "ghcr.io/astral-sh/uv:python3.12-bookworm-slim"
        entrypoint   = ["/bin/sh", "-c"]
        network_mode = "bridge"
      }

      env {
        HARNESS_RANGE_ROLE = "observer"
      }

      resources {
        cpu    = 300
        memory = 256
      }
    }
  }
}
