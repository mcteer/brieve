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
#
# SIBLING: `authoring-tier.nomad.hcl` (038). It differs in exactly two ways and both matter —
# it MOUNTS its subject read-only (a repository is not payload-scale, as the delta below is),
# and its analyzer's egress allowlist is EMPTY (it reads a mount and fetches nothing, where
# this one fetches the pinned upstream). A change to one that does not need the other is
# probably wrong.

variable "cni_bridge" {
  type        = bool
  default     = true
  description = "Nomad CNI group bridge when true; see authoring-tier.nomad.hcl for Darwin."
}

job "analysis-tier" {
  # 017's deployment lane. Every job definition must be a declared subject or an
  # explicitly excluded one — coverage a process opts into is fail-open, and the
  # process nobody remembered to enrol is exactly the one nobody remembered to cover.
  #
  # 037's hardened untrusted-content isolation tier. Dispatched per analysis, so the
  # deployment lane does not stand it up; the intake rows drive it.
  meta {
    harness_surface     = "true"
    harness_shape       = "dispatched"
    harness_covered_by  = "tests/conformance/intake/"
    harness_lane_starts = "false"
  }
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

    # BRIDGE, NEVER HOST. Host mode would put hostile-by-assumption content on the machine's
    # own network. CNI group bridge when fingerprinted; otherwise Docker network_mode=bridge.
    dynamic "network" {
      for_each = var.cni_bridge ? [1] : []
      content {
        mode = "bridge"
      }
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
        labels = {
          "com.docker.compose.project" = "brieve-local"
          "com.docker.compose.service"  = "analysis-tier"
        }

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
