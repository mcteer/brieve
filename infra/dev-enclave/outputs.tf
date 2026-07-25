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
