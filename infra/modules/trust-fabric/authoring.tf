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
# READ BY THE PUBLISHING TASK ONLY. The analysing task holds no attested identity at all
# (`authoring-tier.nomad.hcl` declares no `identity` stanza for it), so it cannot reach this path
# even if a policy allowed it to. Two controls, and the absence is the stronger one.

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

# Bound to the publishing task's workload identity. The analysing task's role is deliberately
# absent rather than present-and-empty: a role that exists with no capabilities still says
# somebody thought this task might need one, and the design says it must not.
resource "vault_jwt_auth_backend_role" "authoring_publisher" {
  backend         = vault_jwt_auth_backend.workload.path
  role_name       = "authoring-publisher"
  role_type       = "jwt"
  user_claim      = "nomad_job_id"
  bound_audiences = ["vault.io"]

  bound_claims = {
    nomad_job_id = "authoring-tier"
    nomad_task   = "proposer"
  }

  token_policies = [vault_policy.authoring_publisher.name]
  # An hour, matching the identity's own TTL. Long enough to open a proposal, short enough that
  # a leaked token is a window rather than a key.
  token_ttl     = 3600
  token_max_ttl = 3600
}
