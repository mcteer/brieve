# SPDX-License-Identifier: Apache-2.0
output "vault_addr" { value = module.substrate.vault_address }
output "jwt_auth_path" { value = module.trust_fabric.jwt_auth_path }
output "database_creds_path" { value = module.trust_fabric.database_creds_path }
output "registered_agents" { value = module.trust_fabric.registered_agents }

# The SC-001 evidence.
output "configuration_digest" { value = module.trust_fabric.configuration_digest }
output "configuration_elements" { value = module.trust_fabric.configuration_elements }

# FR-010: each of the four items, with its disposition and reason. Deferral is
# acceptable; silence is the failure this exists to prevent.
output "production_posture" { value = module.trust_fabric.production_posture }

# Read by enclave-up between phases, to hand back into the substrate.
output "listener_certificate" { value = module.trust_fabric.listener_certificate }
output "listener_ca_chain" { value = module.trust_fabric.listener_ca_chain }
output "listener_private_key" {
  value     = module.trust_fabric.listener_private_key
  sensitive = true
}
