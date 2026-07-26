# SPDX-License-Identifier: Apache-2.0
# The same three outputs as every other substrate. That sameness is the interface.

output "vault_address" { value = var.vault_address }
output "nomad_jwks_url" { value = var.nomad_jwks_url }
output "database_endpoint" { value = var.database_endpoint }
