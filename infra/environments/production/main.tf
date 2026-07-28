# SPDX-License-Identifier: Apache-2.0
#
# Production root: substrate-vm + trust-fabric.
#
# Compare this file with ../dev/main.tf. The ONLY differences are which substrate
# module is composed and which profile is selected. That the delta is visible in the file
# layout — rather than hidden in a conditional inside a shared file — is what makes
# FR-002 checkable by reading rather than by tracing.

terraform {
  required_version = ">= 1.9"
  required_providers {
    vault = { source = "hashicorp/vault", version = "~> 4.4" }
  }
}

provider "vault" {
  address = module.substrate.vault_address
  token   = var.vault_token

  # Production's trust store is HTTPS by definition, so the provider must trust its CA.
  # Explicit rather than ambient: leaving it to VAULT_CACERT in the caller's environment
  # means an apply that works for whoever set it and fails for everyone else, with
  # "failed to lookup token" — which names neither TLS nor the CA.
  ca_cert_file = var.ca_cert_file
}

module "substrate" {
  source = "../../modules/substrate-vm"

  vault_address     = var.vault_address
  nomad_jwks_url    = var.nomad_jwks_url
  database_endpoint = var.database_endpoint
}

module "trust_fabric" {
  source = "../../modules/trust-fabric"

  nomad_jwks_url    = module.substrate.nomad_jwks_url
  database_endpoint = module.substrate.database_endpoint
  profile           = "production"
  # Production is never plaintext. Not a variable: a deployment that can turn TLS
  # off is a deployment where someone will.
  enable_tls = true

  agent_definitions = var.agent_definitions
  role_bindings     = var.role_bindings
}
