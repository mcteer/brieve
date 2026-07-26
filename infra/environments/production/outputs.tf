# SPDX-License-Identifier: Apache-2.0
output "vault_addr" { value = module.substrate.vault_address }
output "jwt_auth_path" { value = module.trust_fabric.jwt_auth_path }
output "database_creds_path" { value = module.trust_fabric.database_creds_path }
output "registered_agents" { value = module.trust_fabric.registered_agents }

# The SC-001 evidence.
output "configuration_digest" { value = module.trust_fabric.configuration_digest }
output "configuration_elements" { value = module.trust_fabric.configuration_elements }
