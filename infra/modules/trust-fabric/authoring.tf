# SPDX-License-Identifier: Apache-2.0
#
# THE AUTHORING CREDENTIAL PATH (038, ADR-0062) — Principle IV's THIRD named exception.
#
# The constitution's exception list was closed at two; this is the third, amended into
# Principle IV in the same change rather than argued out of the enumeration. Arguing the clause
# does not bite — it bounds credentials "to anything it manages", and we do not manage the
# requester's repository — was genuinely available, and it is the narrowing v1.4.0 declined when
# the model vendor credential arrived. A closed list that grows by interpretation is not one.
#
# WHAT IS HELD, AND WHAT IS NOT. The App PRIVATE KEY lives here and nowhere else. No workload
# persists it, no jobspec carries it, and what a run receives is never this — it is a short-lived
# installation token minted from it. The key is a standing credential in the trust store; the
# token is manufactured per task and evaporates with it, which is the same shape as the database
# credentials every other allocation takes.
#
# READ BY THE PUBLISHING TASK ONLY. The analysing task holds an attested identity for audit
# and the model matrix (role `authoring-analyzer` below) but that role's policies never name
# this path — so it cannot mint an installation token even if it tried. Two controls: the
# publisher role is bound to `nomad_task = "proposer"`, and the analyzer role omits this
# policy entirely.

resource "vault_kv_secret_v2" "authoring_vcs_app" {
  mount = vault_mount.harness_authority.path
  name  = "authoring/vcs-app"

  # Placeholder. The real key is written out of band by an operator, never by an apply — an
  # apply that carried it would put it in state, and Terraform state is a second copy of every
  # secret it manages. `lifecycle.ignore_changes` below is what keeps the apply from reverting
  # the operator's write on the next run.
  data_json = jsonencode({
    app_id          = var.authoring_app_id
    installation_id = var.authoring_installation_id
    private_key     = "SET-OUT-OF-BAND"
  })

  lifecycle {
    # The apply establishes the PATH and its policy; the operator establishes the VALUE. Without
    # this, every apply would overwrite a real key with the placeholder above and the failure
    # would present as an authentication outage with no obvious cause — the shape
    # `terraform-apply-clobbers-the-model-credential` already cost this project once.
    ignore_changes = [data_json]
  }
}

# Read-only, and scoped to the one path. A policy naming the mount would let the publishing
# task read every ceiling in the harness-authority store — which is the trust fabric reading
# itself, and is what `handlers.py` records refusing for the same reason.
resource "vault_policy" "authoring_publisher" {
  name = "authoring-publisher"

  policy = <<-EOT
    path "harness-authority/data/authoring/vcs-app" {
      capabilities = ["read"]
    }
  EOT
}

# Bound to the publishing task's workload identity. The analysing task uses a different role
# (below) that cannot read the App key — that split is the control, not "analyzer has no JWT".
resource "vault_jwt_auth_backend_role" "authoring_publisher" {
  backend         = vault_jwt_auth_backend.workload.path
  role_name       = "authoring-publisher"
  role_type       = "jwt"
  user_claim      = "nomad_job_id"
  bound_audiences = ["vault.io"]

  # Parent job id only. Nomad's workload identity carries `authoring-tier`, not the
  # dispatch-derived `authoring-tier/dispatch-*` shown in `nomad job status` (same lesson as
  # `agent-run`). A glob attempt that listed both forms broke analyzer login in the local
  # estate — keep the exact parent id that already works.
  bound_claims = {
    nomad_job_id = "authoring-tier"
    nomad_task   = "proposer"
  }

  # App key + audit DB + fabric reads. The entrypoint always opens Postgres under this role
  # name when HARNESS_AUTHORING_ROLE=proposer; without harness_database the publisher dies
  # in audit.migrate() after the analyzer already did the work.
  token_policies = [
    vault_policy.authoring_publisher.name,
    vault_policy.harness_database.name,
    vault_policy.harness_authority_read.name,
  ]
  # An hour, matching the identity's own TTL. Long enough to open a proposal, short enough that
  # a leaked token is a window rather than a key.
  token_ttl     = 3600
  token_max_ttl = 3600
}

# Analyzer: audit + matrix + model credential. Never the App key (authoring_publisher policy).
resource "vault_jwt_auth_backend_role" "authoring_analyzer" {
  backend         = vault_jwt_auth_backend.workload.path
  role_name       = "authoring-analyzer"
  role_type       = "jwt"
  user_claim      = "nomad_job_id"
  bound_audiences = ["vault.io"]

  bound_claims = {
    nomad_job_id = "authoring-tier"
    nomad_task   = "analyzer"
  }

  token_policies = [
    vault_policy.harness_database.name,
    vault_policy.harness_authority_read.name,
    vault_policy.model_credential_read.name,
  ]
  token_ttl     = 3600
  token_max_ttl = 3600
}
