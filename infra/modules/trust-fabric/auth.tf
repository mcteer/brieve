# SPDX-License-Identifier: Apache-2.0
#
# Attestation. The scheduler signs a workload identity; Vault verifies it against the
# scheduler's JWKS. No shared secret, nothing to place in a jobspec.

resource "vault_jwt_auth_backend" "workload" {
  path               = "nomad"
  type               = "jwt"
  jwks_url           = var.nomad_jwks_url
  jwt_supported_algs = ["RS256"]
  description        = "Workload identity (ADR-0048)"
}

# Per-definition agent roles. An agent's ceiling bounds what a model-chosen tool call
# may reach — and deliberately does NOT include the state store: see policies.tf.
resource "vault_jwt_auth_backend_role" "agent" {
  for_each = var.agent_definitions

  backend                 = vault_jwt_auth_backend.workload.path
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
  # Short by construction. A run outliving this re-authenticates; it never replays,
  # because on resume the allocation is new and so is its identity (ADR-0026).
  token_ttl  = 300
  token_type = "service"
}

# The platform's own identity, distinct from any agent's. The harness process may reach
# its state store; the agent running inside it may not.
resource "vault_jwt_auth_backend_role" "harness" {
  backend                 = vault_jwt_auth_backend.workload.path
  role_name               = "harness"
  role_type               = "jwt"
  bound_audiences         = ["vault.io"]
  user_claim              = "/nomad_job_id"
  user_claim_json_pointer = true

  # Without the bound claim, ANY workload could assume this role and the attestation
  # would be decorative — it would prove something was scheduled, not what.
  bound_claims = {
    nomad_job_id = var.harness_job_id
  }

  token_policies = [vault_policy.harness_database.name]
  token_ttl      = 300
  token_type     = "service"
}

# The conformance suite runs as its own workload with its own identity. That is what
# lets the durability rows exercise the attestation path rather than sit beside it.
resource "vault_jwt_auth_backend_role" "conformance" {
  backend                 = vault_jwt_auth_backend.workload.path
  role_name               = "conformance"
  role_type               = "jwt"
  bound_audiences         = ["vault.io"]
  user_claim              = "/nomad_job_id"
  user_claim_json_pointer = true

  bound_claims = {
    nomad_job_id = var.conformance_job_id
  }

  token_policies = [vault_policy.harness_database.name]
  token_ttl      = 1800
  token_type     = "service"
}
