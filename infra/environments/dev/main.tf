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
}

module "substrate" {
  source        = "../../modules/substrate-docker"
  vault_license = var.vault_license
}

module "trust_fabric" {
  source = "../../modules/trust-fabric"

  nomad_jwks_url    = module.substrate.nomad_jwks_url
  database_endpoint = module.substrate.database_endpoint
  profile           = "development"
  enable_tls        = var.enable_tls

  agent_definitions = var.agent_definitions
}
