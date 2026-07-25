# SPDX-License-Identifier: Apache-2.0
#
# TRUST FABRIC — substrate-independent. This is the load-bearing configuration
# and is intended to apply unchanged against a production Vault.
#
# It implements Principle IV's chain concretely:
#   attested workload identity (Nomad) -> control-plane Vault -> scoped, short-lived token

# Ceiling policies. An agent's authority can never exceed these, whatever a task requests.
resource "vault_policy" "agent_ceiling" {
  for_each = var.agent_definitions
  name     = each.value.ceiling_policy
  policy = join("\n", [
    for p in each.value.allowed_paths :
    "path \"${p}\" { capabilities = [\"read\"] }"
  ])
}

# Nomad workload identity is the attestation. Vault verifies the JWT against
# Nomad's JWKS — no shared secret, nothing to place in a jobspec.
resource "vault_jwt_auth_backend" "nomad" {
  path               = "nomad"
  type               = "jwt"
  jwks_url           = var.nomad_jwks_url
  jwt_supported_algs = ["RS256"]
  description        = "Nomad workload identity (ADR-0048)"
}

resource "vault_jwt_auth_backend_role" "agent_harness" {
  for_each = var.agent_definitions

  backend                 = vault_jwt_auth_backend.nomad.path
  role_name               = each.key
  role_type               = "jwt"
  bound_audiences         = ["vault.io"]
  user_claim              = "/nomad_job_id"
  user_claim_json_pointer = true

  claim_mappings = {
    nomad_namespace = "nomad_namespace"
    nomad_job_id    = "nomad_job_id"
    nomad_task      = "nomad_task"
  }

  token_policies = [each.value.ceiling_policy]
  # Short-lived by construction. A run outliving this re-authenticates; it never
  # replays (ADR-0026). On resume the allocation is new, so its identity is new.
  token_ttl  = 300
  token_type = "service"
}

# Identity entity the registration binds to.
resource "vault_identity_entity" "agent" {
  for_each = var.agent_definitions
  name     = each.key
}

# Vault's agent registry (2.0.3+ent). ADR-0015 calls the control-plane Vault
# "the agent registry and trust fabric" — this is that feature, not a convention
# we implement on top of kv. No Terraform resource exists for it yet, so the
# generic endpoint is used.
resource "vault_generic_endpoint" "agent_registration" {
  for_each = var.agent_definitions

  path                 = "agent-registry/register"
  disable_read         = true
  disable_delete       = true
  ignore_absent_fields = true

  data_json = jsonencode({
    display_name     = each.key
    entity_id        = vault_identity_entity.agent[each.key].id
    description      = each.value.description
    owner            = each.value.owner
    ceiling_policies = [each.value.ceiling_policy]
  })

  depends_on = [vault_policy.agent_ceiling]
}
