# SPDX-License-Identifier: Apache-2.0
output "vault_addr" {
  value       = "http://127.0.0.1:${var.vault_port}"
  description = "Set VAULT_ADDR to this for CLI use."
}

output "jwt_auth_path" {
  value       = vault_jwt_auth_backend.nomad.path
  description = "Auth mount a Nomad workload logs in against: POST /v1/auth/<path>/login"
}

output "registered_agents" {
  value       = keys(var.agent_definitions)
  description = "Agent definitions present in Vault's agent registry."
}

output "database_creds_path" {
  value       = "${vault_mount.database.path}/creds/${vault_database_secret_backend_role.harness.name}"
  description = "Where the harness reads a dynamic Postgres credential, having first authenticated with its workload identity."
}

output "harness_jwt_role" {
  value       = vault_jwt_auth_backend_role.harness.role_name
  description = "JWT auth role the harness job assumes. Bound to the job ID — no other workload may use it."
}
