# SPDX-License-Identifier: Apache-2.0
terraform {
  required_version = ">= 1.9"
  required_providers {
    docker = { source = "kreuzwerker/docker", version = "~> 3.0" }
    vault  = { source = "hashicorp/vault", version = "~> 4.4" }
  }
}

# Substrate provider. In production this is replaced by the cloud provider that
# creates the VM or instance Vault runs on; everything in vault-trust.tf is
# unchanged (ADR-0025: "the substrate is the only permitted delta").
provider "docker" {}

provider "vault" {
  address = "http://127.0.0.1:${var.vault_port}"
  token   = var.vault_token
}
