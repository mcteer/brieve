# SPDX-License-Identifier: Apache-2.0
#
# A governed run, as a scheduled workload.
#
# This is what `NomadDispatcher` dispatches to, and its existence is what makes FR-007a's
# handle mean anything: the API returns a run id because the run is a *thing that outlives
# the request*, not because the surface chose to answer early.
#
# A **parameterized** batch job rather than one job per run. Nomad dispatches an instance
# per invocation with its own metadata, which gives each run its own allocation and — the
# part that matters — its own attested workload identity. 005 made that structural: resume
# is a NEW allocation with a NEW identity, so replaying a pre-disruption credential is
# unavailable rather than merely forbidden.
#
# READ THIS JOBSPEC FOR WHAT IS ABSENT: no token, no password, no DSN, no mounted secret.
# The dispatch carries who the run is for and what it may touch. It carries no authority.
# The allocation presents its identity to Vault and receives a ceiling-scoped token, or it
# does nothing at all.
#
# The task body is `src/surfaces/dispatch/entrypoint.py`. It lived under `tests/harness/`
# until 010 built an identity fabric for it to resolve through — deliberate rather than
# provisional sloppiness: a production entrypoint needs a real IdentityFabric, and no
# implementation of that protocol exists in this repository yet. What this job proves is
# the dispatch and attestation path, which is what 008 owed.

variable "vault_addr" {
  type        = string
  default     = "https://127.0.0.1:8200"
  description = "Where the trust store answers. HTTPS once bring-up has switched the listener."
}

variable "vault_cacert" {
  type        = string
  default     = "/repo/.enclave/ca.pem"
  description = "Control-plane CA, as seen INSIDE the container — the repo is mounted at /repo."
}

variable "repo" {
  type        = string
  description = "Working tree to mount, as for the conformance job."
}

job "agent-run" {
  type = "batch"

  parameterized {
    # Required, because a run with no subject is a run whose audit trail names nobody, and
    # a run with no tenant cannot be scoped when its evidence is read back.
    meta_required = [
      "correlation_id",
      "subject_user_id",
      "tenant_id",
      "agent_definition_id",
      # Resume state. Required rather than optional because a dispatch that omitted them
      # would start a fresh run under a resumed run's correlation id — which looks like a
      # successful resume and re-executes everything the run had already done. A fresh
      # dispatch passes its own correlation id and step 0.
      "run_id",
      "step_index",
    ]

    # OPTIONAL rather than required, and the distinction is the same one that made the
    # resume fields required. Omitting `run_id` silently starts a fresh run under a
    # resumed correlation id — wrong, plausible, and invisible. Omitting the roles
    # produces a run that refuses `no_role_for_subject` before doing anything, which is
    # loud and traceable. Nomad rejects any metadata key declared in neither list, so a
    # key added to the dispatcher and not here fails the dispatch with
    # "unpermitted metadata keys" rather than being silently dropped.
    meta_optional = [
      "requested_tools",
      "subject_roles",
      # Multi-step mode, for rows that need a run still running when something happens to
      # it. Optional because a run that ignores them behaves exactly as before — and Nomad
      # rejects any metadata key declared in neither list, so a key added to the dispatcher
      # and not here fails the dispatch with "unpermitted metadata keys" rather than being
      # silently dropped. Found the hard way in 010.
      "steps",
      # 013: which capability packs the entrypoint loads, comma-separated. Optional — a
      # dispatch naming none behaves exactly as before, and the fixture tools stay.
      "packs",
      # 013: when "1", the entrypoint invokes each requested tool once through the real
      # pipeline. Opt-in, because every pre-013 dispatched row asserts a trail this would
      # append TOOL_OUTCOME events to.
      "invoke_tools",
    ]
  }

  group "run" {
    # A failed run is a failed run. Rescheduling would give a second allocation — and
    # therefore a second identity — to work the first was already fenced out of.
    reschedule {
      attempts  = 0
      unlimited = false
    }

    restart {
      attempts = 0
    }

    task "harness" {
      driver = "docker"

      # The attestation, and the only thing this workload is given. `aud` must match the
      # Vault role's bound_audiences and the job id its bound_claims, or any workload
      # could assume the role and the identity check would be decorative.
      identity {
        name = "vault"
        aud  = ["vault.io"]
        env  = true
        file = true
        # An identity without an expiry is a standing credential wearing a different hat.
        ttl         = "1h"
        change_mode = "restart"
      }

      config {
        image        = "python:3.12-slim"
        entrypoint   = ["/bin/sh", "-c"]
        network_mode = "host"

        mount {
          type     = "bind"
          source   = var.repo
          target   = "/repo"
          readonly = false
        }

        # No shell parameter expansion: Nomad interpolates ${...} before the shell sees
        # it, so a default like ${VAR:-x} fails to parse with an error about
        # interpolation rather than about the script.
        args = [
          "set -e; cd /repo; export PYTHONPYCACHEPREFIX=/tmp/pycache; pip install --quiet --disable-pip-version-check uv; uv run --extra adapters --extra surfaces python -m surfaces.dispatch.entrypoint"
        ]
      }

      # Cores, not MHz. This node fingerprints its CPU total as a couple of dozen MHz, so
      # the DEFAULT MHz-based reservation (100) exceeds the whole node and every dispatch
      # sits queued with "Resources exhausted" — a placement failure that looks nothing
      # like a resource declaration problem. The other jobs in this tree all use `cores`
      # for the same reason.
      resources {
        cores  = 1
        memory = 1024
      }

      env {
        VAULT_ADDR   = var.vault_addr
        VAULT_CACERT = var.vault_cacert

        # Outside the mounted tree, so running a dispatched run does not rebuild the
        # developer's virtualenv against the container's interpreter and back again.
        UV_PROJECT_ENVIRONMENT = "/tmp/venv"

        # What the dispatch asked for. Metadata, not authority.
        RUN_CORRELATION_ID  = "${NOMAD_META_correlation_id}"
        RUN_SUBJECT_USER_ID = "${NOMAD_META_subject_user_id}"
        RUN_TENANT_ID       = "${NOMAD_META_tenant_id}"
        RUN_DEFINITION_ID   = "${NOMAD_META_agent_definition_id}"
        RUN_REQUESTED_TOOLS = "${NOMAD_META_requested_tools}"

        # The roles the dispatching surface resolved from this subject's verified claims.
        # Metadata, like everything above it — it says what the surface established, and
        # the run still resolves what those roles MEAN from the trust fabric. Carrying the
        # resolved scope here instead would let a dispatcher grant authority by writing it
        # into a jobspec, which is the shape ADR-0048 exists to close.
        RUN_SUBJECT_ROLES = "${NOMAD_META_subject_roles}"

        # Empty unless a row asks for them, in which case the run brackets that many steps.
        RUN_STEPS = "${NOMAD_META_steps}"
        RUN_PACKS = "${NOMAD_META_packs}"
        RUN_INVOKE_TOOLS = "${NOMAD_META_invoke_tools}"
        RUN_ID              = "${NOMAD_META_run_id}"
        RUN_STEP_INDEX      = "${NOMAD_META_step_index}"
      }
    }
  }
}
