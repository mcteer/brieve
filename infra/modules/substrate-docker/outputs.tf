# SPDX-License-Identifier: Apache-2.0
#
# Exactly three outputs. A fourth means the substrate boundary has moved — a deliberate
# change to contracts/module-interface.md, not a variable someone adds.

output "vault_address" {
  value = "${local.scheme}://127.0.0.1:${var.vault_port}"
}

output "nomad_jwks_url" {
  # As reachable FROM the trust store's container, not from the operator's shell.
  value = "http://host.docker.internal:4646/.well-known/jwks.json"
}

output "database_endpoint" {
  value = "host.docker.internal:5432"
}
