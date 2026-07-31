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

  # Both jurisdictions: the state store to write its own record, and the harness-domain
  # ceiling to know what it may call. Read-only on the second — a run that could write its
  # own ceiling would be the escalation Principle IV exists to make structurally
  # unavailable.
  token_policies = [
    vault_policy.harness_database.name,
    vault_policy.harness_authority_read.name,
  ]
  token_ttl  = 300
  token_type = "service"
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

  # Both, because the conformance rows exercise the write path and the read path: the
  # evidence rows have to draw a real SELECT-only credential to prove Postgres refuses a
  # write through it. Proving that against a fake connection would prove nothing.
  token_policies = [
    vault_policy.harness_database.name,
    vault_policy.evidence_database.name,
    vault_policy.harness_authority_read.name,
  ]
  token_ttl  = 1800
  token_type = "service"
}

# Dispatched agent runs.
#
# Separate from the conformance role because they are separate things that happen to want
# the same database access today: one is a merge gate, the other is the product. Merging
# them would mean widening the gate's authority to widen a run's, or the reverse, which is
# exactly the coupling per-task authority exists to avoid.
#
# `bound_claims_type = "glob"` so both the parent id and any derived dispatch id are
# admissible. The identity presents the PARENT id, which is not what `nomad job status`
# shows — binding only the derived form fails every login with "claim nomad_job_id does not
# match any associated bound claim values" while the role looks correctly configured.
resource "vault_jwt_auth_backend_role" "agent_run" {
  backend                 = vault_jwt_auth_backend.workload.path
  role_name               = "agent-run"
  role_type               = "jwt"
  bound_audiences         = ["vault.io"]
  user_claim              = "/nomad_job_id"
  user_claim_json_pointer = true

  bound_claims_type = "glob"
  bound_claims = {
    nomad_job_id = join(",", var.agent_run_job_id_patterns)
  }

  # The harness-domain jurisdiction too, as of 010: a dispatched run resolves its own
  # ceiling, user scope, and policy from the trust fabric. Read-only — a run that could
  # write its own ceiling would be the escalation Principle IV makes structurally
  # unavailable, and it would be one line away.
  token_policies = [
    vault_policy.harness_database.name,
    vault_policy.harness_authority_read.name,
    # 013: the agent secret space pack tools read. Role-level by declared limitation —
    # see the policy's own comment; per-definition narrowing is ADR-0044's translation.
    vault_policy.agent_pack_secrets.name,
  ]
  token_ttl  = 3600
  token_type = "service"
}

# The persistent MCP service.
#
# Separate from `harness` and `agent-run` because it is a separate thing that happens to
# want the same database access: it reads dependency health, writes what its checker
# observed, and verifies evidence-stream integrity. Merging the roles would mean widening
# one workload's authority to widen another's, which is the coupling per-task authority
# exists to avoid.
#
# It carries `harness_database` and NOT `evidence_database`: integrity verification runs
# under the run role, because `audit_stream_heads` deliberately carries no grant for the
# evidence role — a read path able to see the heads could learn what it would need to
# forge.
resource "vault_jwt_auth_backend_role" "mcp" {
  backend                 = vault_jwt_auth_backend.workload.path
  role_name               = "mcp"
  role_type               = "jwt"
  bound_audiences         = ["vault.io"]
  user_claim              = "/nomad_job_id"
  user_claim_json_pointer = true

  bound_claims = {
    nomad_job_id = var.mcp_job_id
  }

  token_policies = [
    vault_policy.harness_database.name,
    vault_policy.harness_authority_read.name,
    # 015: the mcp service is the only workload that ships to the second copy, because it
    # is the only one running the supervisory loop. One path, read-only — and not the
    # jobspec's env block, where the credential's SELECT half would be readable by anyone
    # with scheduler access.
    vault_policy.audit_egress_credential.name,
  ]
  # Longer than a batch job's, because this one is long-lived by design — and still a TTL
  # rather than none, which is the difference between a re-issued identity and a standing
  # credential.
  token_ttl  = 3600
  token_type = "service"
}
