# SPDX-License-Identifier: Apache-2.0
#
# THE AUTHORING TIER (038, FR-005; ADR-0038, ADR-0062, ADR-0064).
#
# Sibling to `analysis-tier.nomad.hcl`, which is 037's. They differ in exactly two ways and both
# matter: this one MOUNTS its subject (a repository is not payload-scale), and this one's
# analyzer has an EMPTY egress allowlist (it reads a mount and fetches nothing). Read them
# together — a change to one that does not need the other is probably wrong.
#
# ONE GROUP, TWO SEQUENTIAL TASKS. `analyzer` runs everything that needs the subject — reading,
# authoring, composing, containment — and exits. `proposer` publishes what already passed.
# Identity, `env` and `config.mount` are per-task in Nomad, so the two hold genuinely different
# authority and see genuinely different filesystems, while one allocation means ONE run and ONE
# correlation ID (Principle IX: one correlation ID, walkable both directions).
#
# THE `prestart` LIFECYCLE IS THE ONLY CONTROL THAT SEQUENCES THEM, and this is not obvious.
# `holder_identity` in the entrypoint derives from NOMAD_ALLOC_ID — "this allocation's identity,
# for the lease" — which is PER-ALLOCATION, shared by every task in a group. So these two tasks
# are the SAME lease holder: run concurrently they would both pass `assert_held` and race on the
# checkpoint, each overwriting the other's step index, rather than fencing each other. An
# earlier draft justified this ordering by lease fencing; that premise was wrong. The lease will
# not catch a violation here, which is why a conformance row asserts the lifecycle directly.
#
# AND WHEN CNI BRIDGE IS ON, THE NETWORK NAMESPACE IS SHARED. A group in Nomad bridge mode has
# one namespace, so the analyzer sits somewhere the version-control host is reachable even with
# an empty allowlist. Network separation between these two tasks is NOT a control either way
# (CNI shared namespace, or separate Docker bridges on Darwin). What contains the analyzer is:
# nothing egressing in its effective scope (RUN_REQUESTED_TOOLS below), no credential in its
# task, and the declared allowlist. Three controls, not four — said here so nobody later claims
# the fourth.
variable "repo" {
  type        = string
  description = "Working tree to mount at /repo for the dispatch entrypoint (same as agent-run)."
}

variable "vault_addr" {
  type        = string
  default     = "https://host.docker.internal:8200"
  description = <<-DESC
    Trust store as seen from this container. Defaults for Docker bridge (never loopback):
    `127.0.0.1` inside the container is the container itself. Same posture as mcp-surface.
  DESC
}

variable "vault_cacert" {
  type        = string
  default     = "/repo/.enclave/ca.pem"
  description = "Control-plane CA inside the container (repo is mounted at /repo)."
}

variable "db_host" {
  type        = string
  default     = "host.docker.internal"
  description = "Postgres as seen from bridge-mode tasks. Host-mode jobs use 127.0.0.1."
}

variable "cni_bridge" {
  type        = bool
  default     = true
  description = <<-DESC
    Nomad group `network { mode = "bridge" }` (CNI). Required posture on Linux clients that
    have the CNI reference plugins fingerprinted.

    Local Darwin agents (Nomad on macOS + OrbStack/Docker) cannot run Linux CNI plugins, so
    bring-up passes false there. Tasks still set Docker `network_mode = "bridge"` — never
    host — which keeps hostile-by-assumption content off the machine's own network. Group
    CNI bridge is what shares one namespace across tasks; without it, tasks are separate
    Docker bridges. Network separation between analyzer and proposer was already not a
    control (see header); the alloc directory is.
  DESC
}

variable "image" {
  type        = string
  default     = "brieve/authoring-runtime:local"
  description = <<-DESC
    Task image for both analyzer and proposer. Must carry pinned `git` and `gh` (ADR-0066 /
    041 R8) and pinned `terraform` (047 / ADR-0047) — the proposer fails `tooling_missing`
    at start if git or gh is absent; the analyzer fails the same way if terraform is
    absent. Built from `infra/images/authoring-runtime/Dockerfile`; `portal-up` /
    `enclave-up` build the local tag before registering this job. Do not revert to a bare
    uv image: that cannot publish or plan.
  DESC
}

variable "vcs_installation" {
  type        = string
  default     = ""
  description = <<-DESC
    GitHub App installation id for publishing (ADR-0062). Becomes RUN_VCS_INSTALLATION on
    the proposer. Empty refuses at publish with "no installation named for publishing".
    Not a secret — pair with the operator-seeded App key at harness-authority/authoring/vcs-app.
  DESC
}

job "authoring-tier" {
  type        = "batch"
  datacenters = ["dc1"]

  # Dispatched by `NomadDispatcher`, which takes a `job_id` but carries the agent-run meta
  # contract. A jobspec without these keys cannot be dispatched by the dispatcher that exists.
  parameterized {
    payload       = "optional"
    meta_required = [
      "correlation_id",
      "tenant_id",
      "agent_definition_id",
      "run_id",
      "subject_path",
      "subject_user_id",
    ]
    meta_optional = [
      "packs",
      "steps",
      "subject_roles",
      "invoke_tools",
      # 020 / 047: fixture write cell replays this instead of calling a vendor. Ignored when
      # the bound cell names a live provider (matrix chooses the branch, not this meta).
      "choice_recording",
      # 041 handoff: compose needs the forge id and the commit the subject was acquired at.
      "target_repository",
      "base_commit",
    ]
  }

  group "authoring" {
    # ONE ATTEMPT. A retried analysis of hostile content is a second execution of hostile
    # content, and the stage fails closed anyway.
    restart { attempts = 0 }

    # BRIDGE VIA CNI WHEN AVAILABLE — never host. Omitted on Darwin clients (var.cni_bridge);
    # Docker network_mode=bridge on each task still keeps work off the host network.
    dynamic "network" {
      for_each = var.cni_bridge ? [1] : []
      content {
        mode = "bridge"
      }
    }

    task "analyzer" {
      driver = "docker"

      # PRESTART, NOT A SIDECAR: this task runs to completion and exits before `proposer`
      # starts. See the lease note in the header — this stanza is the sequencing, and nothing
      # else enforces it.
      lifecycle {
        hook    = "prestart"
        sidecar = false
      }

      # Workload identity for audit DB + model matrix only. Vault role `authoring-analyzer`
      # omits the App-key policy; `authoring-publisher` is bound to nomad_task=proposer. The
      # control is the role split, not "no JWT at all" — without a JWT the entrypoint cannot
      # open PostgresAuditSink and the analyzer never starts (047 local enclave finding).
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
          "com.docker.compose.service"  = "authoring-analyzer"
        }

        image        = var.image
        # Local tag (`brieve/authoring-runtime:local`) is not on a registry. Without this,
        # Docker tries to pull and fails with "pull access denied" before the task starts.
        # Nomad's default image GC also deletes unused local tags after ~3 minutes —
        # `infra/bin/authoring-image` pins the tag; `infra/nomad/client.hcl` disables GC.
        force_pull   = false
        entrypoint   = ["/bin/sh", "-c"]
        network_mode = "bridge"

        # THE SUBJECT, READ-ONLY. This is not the reversal of 037's no-mount rule that it looks
        # like: that rule meant *do not hand a redirected analyser the platform's own tree*, and
        # this is the requester's. The platform's tree stays unmounted here as it does there.
        #
        # The source is per-dispatch because the subject differs every run — which is exactly
        # why it is VALIDATED before dispatch (`core.authoring.request.resolve_subject_mount`,
        # refusing `subject_is_platform_tree`). A dispatch naming our own tree would satisfy
        # bridge, readonly and repo_mounted=False while mounting what the tier exists to exclude.
        mount {
          type     = "bind"
          source   = "${NOMAD_META_subject_path}"
          target   = "/subject"
          readonly = true
        }

        # Writable like agent-run: uv writes egg-info / venvs under the tree. The subject
        # mount above stays read-only; this is the platform tree, not the customer's.
        mount {
          type     = "bind"
          source   = var.repo
          target   = "/repo"
          readonly = false
        }

        mount {
          type     = "bind"
          source   = "${var.repo}/.enclave/uv-cache"
          target   = "/uv-cache"
          readonly = false
        }

        # THE COMMAND, ADDED BY 041. Until now both tasks declared `entrypoint = /bin/sh -c`
        # and no `args`, so each started a shell with nothing to run — the tier was carefully
        # specified and could not execute. `agent-run.nomad.hcl` has carried its args since it
        # was written; this file never did, and nothing noticed because nothing dispatched it.
        #
        # `--extra adapters --extra surfaces` matches agent-run: the dispatch entrypoint needs
        # the framework binding and the surfaces extra (which is also where `pyjwt[crypto]` is
        # pinned, for the App-key exchange the proposer performs).
        #
        # NO `--extra evals`: this task calls a model through the ordinary run path and needs
        # no scoring machinery, and 027 recorded what happens when an extra is wrong in a
        # deployed allocation — the failure arrives at the last step, in front of a user.
        #
        # TERRAFORM is the Plan oracle (047). Verified at start: a missing binary must not
        # surface as a green fixture plan after the model has already written files.
        args = [
          "set -e; command -v terraform >/dev/null || { echo 'tooling_missing: terraform' >&2; exit 3; }; cd /repo; export PYTHONPYCACHEPREFIX=/tmp/pycache; uv run --extra adapters --extra surfaces python -m surfaces.dispatch.entrypoint"
        ]
      }

      env {
        UV_CACHE_DIR             = "/uv-cache"
        UV_LINK_MODE             = "copy"
        UV_PROJECT_ENVIRONMENT   = "/tmp/venv"
        VAULT_ADDR               = var.vault_addr
        VAULT_CACERT             = var.vault_cacert
        HARNESS_DB_HOST          = var.db_host
        # EMPTY, AND STATIC. 037 allowlists github.com because its analyser FETCHES the pinned
        # upstream. This one is handed a mount and fetches nothing, so inheriting that value
        # would leave a redirected agent holding a private codebase with a route to the one
        # allowlisted host that serves arbitrary user content. FR-005a requires the allowlist be
        # STATIC, not that it keep a particular value — a control can be correctly immutable and
        # wrongly valued.
        HARNESS_EGRESS_ALLOWLIST = ""
        HARNESS_ISOLATION_TIER   = "hardened"

        # TASK SCOPE. `intersect_scopes(user, ceiling, requested, policy)` narrows the ONE
        # ceiling this run resolves — Principle IV: "effective authority = user ∩ agent ceiling ∩
        # task scope ∩ policy", and "task scope may narrow the ceiling". This is what separates
        # the two halves, because one run has one definition and therefore one ceiling: the
        # two-definition shape an earlier draft used was unbuildable here.
        #
        # Absent would be FAIL-CLOSED, not fail-open: the entrypoint reads this into an empty
        # frozenset and the intersection algebra is strict, so a task that forgot to declare its
        # scope would be permitted NOTHING.
        RUN_REQUESTED_TOOLS = "read_subject,author_file"

        HARNESS_AUTHORING_ROLE = "analyzer"
        RUN_CORRELATION_ID     = "${NOMAD_META_correlation_id}"
        RUN_SUBJECT_USER_ID    = "${NOMAD_META_subject_user_id}"
        RUN_SUBJECT_ROLES      = "${NOMAD_META_subject_roles}"
        RUN_TENANT_ID          = "${NOMAD_META_tenant_id}"
        RUN_DEFINITION_ID      = "${NOMAD_META_agent_definition_id}"
        RUN_ID                 = "${NOMAD_META_run_id}"
        RUN_PACKS              = "${NOMAD_META_packs}"
        RUN_STEPS              = "${NOMAD_META_steps}"
        # "1" when the analyzer consults the write-cell model per step. Must not be set with
        # steps=0 — that path invokes every tool once with empty args and kills authoring.
        RUN_INVOKE_TOOLS       = "${NOMAD_META_invoke_tools}"
        # Fixture write cell only — live cells ignore this (020). Empty is a defined behaviour
        # (first permitted tool); a structured recording drives authoring without a vendor.
        RUN_CHOICE_RECORDING   = "${NOMAD_META_choice_recording}"
        RUN_TARGET_REPOSITORY  = "${NOMAD_META_target_repository}"
        RUN_BASE_COMMIT        = "${NOMAD_META_base_commit}"

        # RUN_RESUME IS DELIBERATELY UNSET on both tasks. The entrypoint branches on
        # RUN_RESUME=1 into the revival path, which counts an attempt against
        # RESUME_ATTEMPT_CAP — and this handoff is a planned transition, not a failure. See
        # `proposer` for the continuation mode it uses instead.
      }

      resources {
        cpu    = 500
        memory = 512
      }
    }

    task "proposer" {
      driver = "docker"

      # The identity the analyzer does not have. Read under this task's own attestation, per
      # task, never persisted (ADR-0062).
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
          "com.docker.compose.service"  = "authoring-proposer"
        }

        image        = var.image
        force_pull   = false
        entrypoint   = ["/bin/sh", "-c"]
        network_mode = "bridge"

        # NO SUBJECT MOUNT. This task never holds the analysed content — it receives a finished,
        # contained proposal through the shared allocation directory and publishes it. That is
        # strictly safer than mounting the subject twice: the task holding the credential holds
        # only bytes that already passed containment.

        mount {
          type     = "bind"
          source   = var.repo
          target   = "/repo"
          readonly = false
        }

        mount {
          type     = "bind"
          source   = "${var.repo}/.enclave/uv-cache"
          target   = "/uv-cache"
          readonly = false
        }

        # THE COMMAND (041), and it VERIFIES ITS TOOLING FIRST.
        #
        # `git` and `gh` are this task's publishing path (ADR-0066). The base image is a Python
        # image and carries neither reliably, so the task fails `tooling_missing` at start
        # rather than at the last step of a run that already did all its analysis. A runtime
        # `apt-get install` was the obvious alternative and is refused: an unpinned network
        # fetch inside a tier that processes untrusted repository content is exactly what the
        # static-allowlist posture exists to prevent.
        args = [
          "set -e; command -v git >/dev/null || { echo 'tooling_missing: git' >&2; exit 3; }; command -v gh >/dev/null || { echo 'tooling_missing: gh' >&2; exit 3; }; cd /repo; export PYTHONPYCACHEPREFIX=/tmp/pycache; uv run --extra adapters --extra surfaces python -m surfaces.dispatch.entrypoint"
        ]
      }

      env {
        UV_CACHE_DIR             = "/uv-cache"
        UV_LINK_MODE             = "copy"
        UV_PROJECT_ENVIRONMENT   = "/tmp/venv"
        VAULT_ADDR               = var.vault_addr
        VAULT_CACERT             = var.vault_cacert
        HARNESS_DB_HOST          = var.db_host
        HARNESS_EGRESS_ALLOWLIST = "github.com"
        HARNESS_ISOLATION_TIER   = "standard"

        # Task scope again: this half may publish and may not author or read the subject.
        RUN_REQUESTED_TOOLS = "open_proposal"

        HARNESS_AUTHORING_ROLE = "proposer"
        RUN_CORRELATION_ID     = "${NOMAD_META_correlation_id}"
        RUN_SUBJECT_USER_ID    = "${NOMAD_META_subject_user_id}"
        RUN_SUBJECT_ROLES      = "${NOMAD_META_subject_roles}"
        RUN_TENANT_ID          = "${NOMAD_META_tenant_id}"
        RUN_DEFINITION_ID      = "${NOMAD_META_agent_definition_id}"
        RUN_ID                 = "${NOMAD_META_run_id}"
        RUN_PACKS              = "${NOMAD_META_packs}"
        RUN_STEPS              = "${NOMAD_META_steps}"
        RUN_INVOKE_TOOLS       = "${NOMAD_META_invoke_tools}"

        # THE CONTINUATION MODE, not a resume. `resume_run` counts attempts against
        # RESUME_ATTEMPT_CAP = 5 and stops the run terminally past it, so routing a designed-in
        # handoff through it would spend attempt 1 of 5 on EVERY healthy run — leaving a
        # genuinely interrupted one with four revivals where every other run type has five, and
        # making the trail read "attempt 2 of 5" for a run that never failed.
        #
        # RUN_CONTINUE loads the blob and the grant, manufactures fresh authority under THIS
        # task's identity, resumes step accounting at the checkpointed index, and does not
        # increment resume_count. Re-authentication is not optional: `resume_run` was the only
        # place authority was re-manufactured, and Principle IV requires "resume re-authenticates,
        # never replays".
        RUN_CONTINUE = "1"

        # Installation id only (ADR-0062). The App private key stays in Vault; this names which
        # installation `token_for` mints against. Empty → proposer exits before forge contact.
        RUN_VCS_INSTALLATION = var.vcs_installation
      }

      resources {
        cpu    = 500
        memory = 512
      }
    }
  }
}
