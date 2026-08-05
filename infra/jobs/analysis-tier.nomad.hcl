# SPDX-License-Identifier: Apache-2.0
#
# THE HARDENED UNTRUSTED-CONTENT ISOLATION TIER (037, FR-006; ADR-0038).
#
# ADR-0038 named this tier in 2026-07 — "repository analysis runs in the hardened
# untrusted-content isolation tier... application code is adversarial input, and the platform
# treats it that way regardless of who supplied it" — and nothing implemented it. 037's first
# analyze pass found the task list building a narrow CEILING in its place, which is a
# different thing: a ceiling bounds what a definition may CALL, a tier bounds what the process
# can REACH.
#
# Every clause below is a reach property. None is expressible as a ceiling, which is why this
# file has to exist rather than being folded into a definition's registration.
job "analysis-tier" {
  type        = "batch"
  datacenters = ["dc1"]

  parameterized {
    payload       = "required"   # the delta, delivered as input — never fetched from disk
    meta_required = ["candidate_digest", "correlation_id"]
  }

  group "analysis" {
    # ONE ATTEMPT. A retried analysis of hostile content is a second execution of hostile
    # content, and the stage fails closed anyway (FR-024) — a candidate whose analysis could
    # not complete is blocked, not retried until it passes.
    restart { attempts = 0 }

    network {
      # BRIDGE, NEVER HOST. `portal.nomad.hcl` records finding the same setting wrong for the
      # opposite reason — host mode shares the Docker VM's network namespace, which made a
      # browser-facing surface unreachable. Here the consequence runs the other way: a
      # workload reading hostile-by-assumption content would sit on the machine's own network,
      # beside every other allocation. This is the single most important line in the file.
      mode = "bridge"
    }

    task "analyzer" {
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
        image        = "ghcr.io/astral-sh/uv:python3.12-bookworm-slim"
        entrypoint   = ["/bin/sh", "-c"]
        network_mode = "bridge"

        # NO REPOSITORY MOUNT, and this is the clause most likely to be "temporarily" added
        # back for convenience. Every other job here mounts `/repo` because its work is the
        # repository's work. This one's subject is a delta that arrives as payload, so a mount
        # would hand a redirected analyzer the whole tree to read and the packs to write —
        # which is exactly the reachability the tier exists to remove.
        #
        # The `[upstream]` diff is the payload. Nothing else is on disk.
      }

      # EGRESS ALLOWLIST. The analyzer may reach the pinned source and nothing else. Empty
      # would also be correct and is stricter than required; what is forbidden is an open
      # egress posture, because an analyzer that can reach anywhere is one a successful
      # redirection has somewhere to send to.
      env {
        HARNESS_EGRESS_ALLOWLIST = "github.com"
        HARNESS_ISOLATION_TIER   = "hardened"
      }

      resources {
        cpu    = 500
        memory = 512
      }
    }
  }
}
