# SPDX-License-Identifier: Apache-2.0
#
# SUBSTRATE — production shape: the trust store on an operator-managed host rather than
# a workstation container.
#
# THIS PLANS WITHOUT CLOUD CREDENTIALS, deliberately. SC-001 compares the configuration
# two substrates produce, and a substrate that cannot plan offline makes the feature's
# central criterion unverifiable in development — which is exactly what it would then
# never be checked. Endpoints are operator-supplied inputs rather than resources this
# module creates, so no authenticating provider is involved.
#
# What this module is NOT: a cloud deployment. Creating the host — instance, network,
# volume — belongs to whatever provisions infrastructure at the operator's site. This
# module's job is to state where the pieces are and to prove that stating it changes
# nothing about the trust fabric.

terraform {
  required_providers {
    terraform = { source = "terraform.io/builtin/terraform" }
  }
}

# Recorded so the arrangement is explicit rather than implied by absence.
resource "terraform_data" "substrate_contract" {
  input = {
    vault_address         = var.vault_address
    nomad_jwks_url        = var.nomad_jwks_url
    database_endpoint     = var.database_endpoint
    scheduled_trust_store = false # ADR-0048: never, on any substrate
  }
}
