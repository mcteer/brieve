# SPDX-License-Identifier: Apache-2.0
#
# Exactly three outputs. A fourth means the substrate boundary has moved — a deliberate
# change to contracts/module-interface.md, not a variable someone adds.

output "vault_address" {
  value = "${local.scheme}://127.0.0.1:${var.vault_port}"
}

output "nomad_jwks_url" {
  # As reachable FROM the trust store's container, not from the operator's shell.
  value = var.vault_host_network ? "http://127.0.0.1:4646/.well-known/jwks.json" : "http://host.docker.internal:4646/.well-known/jwks.json"
}

output "database_endpoint" {
  value = var.vault_host_network ? "127.0.0.1:5432" : "host.docker.internal:5432"
}

output "collector_endpoint" {
  # The second copy (015), again as reachable FROM the trust store's container. It is a
  # scheduled job rather than a container this module creates, so only its address lives
  # here — but the address has to be resolved the same way, and splitting that switch
  # across two modules is how one of them ends up wrong.
  value = var.vault_host_network ? "127.0.0.1:5433" : "host.docker.internal:5433"
}
