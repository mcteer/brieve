# SPDX-License-Identifier: Apache-2.0
#
# Development root: substrate-docker + trust-fabric.
#
# Compare this file with ../production/main.tf. The ONLY differences are which substrate
# module is composed and which profile is selected. That the delta is visible in the file
# layout — rather than hidden in a conditional inside a shared file — is what makes
# FR-002 checkable by reading rather than by tracing.

terraform {
  required_version = ">= 1.9"
  required_providers {
    docker = { source = "kreuzwerker/docker", version = "~> 3.0" }
    vault  = { source = "hashicorp/vault", version = "~> 4.4" }
  }
}

provider "docker" {}

provider "vault" {
  address = module.substrate.vault_address
  token   = var.vault_token

  # Explicit rather than ambient. Once the listener is on TLS the provider must trust the
  # control plane's CA, and leaving that to VAULT_CACERT in the caller's environment
  # means an apply that works for whoever set it and fails for everyone else — with
  # "failed to lookup token", which names neither TLS nor the CA.
  ca_cert_file = var.ca_cert_file
}

module "substrate" {
  source             = "../../modules/substrate-docker"
  vault_host_network = var.vault_host_network
  vault_license      = var.vault_license

  tls_certificate = var.tls_certificate
  tls_private_key = var.tls_private_key
}

module "trust_fabric" {
  source = "../../modules/trust-fabric"

  nomad_jwks_url     = module.substrate.nomad_jwks_url
  database_endpoint  = module.substrate.database_endpoint
  collector_endpoint = module.substrate.collector_endpoint
  profile            = "development"
  enable_tls         = var.enable_tls

  agent_definitions   = var.agent_definitions
  role_bindings       = var.role_bindings
  definition_policies = var.definition_policies
}
