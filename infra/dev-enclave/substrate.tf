# SPDX-License-Identifier: Apache-2.0
#
# SUBSTRATE LAYER — the only part that differs between dev and production
# (ADR-0025). Here Vault runs as a local container; in production the same
# configuration in vault-trust.tf is applied to a Vault on customer infra.
#
# Vault is deliberately NOT a Nomad job. Two independent reasons (ADR-0048):
#   1. Containment — the identity record must not live in the substrate whose
#      access control it exists to constrain (ADR-0015).
#   2. Circularity — Nomad is itself a Vault client, so Vault-under-Nomad has
#      no cold-start order that terminates.

resource "docker_image" "vault" {
  name         = var.vault_image
  keep_locally = true
}

resource "docker_container" "vault" {
  name  = "brieve-dev-vault"
  image = docker_image.vault.image_id
  # Enterprise rejects "inmem" storage outright, so raft is required even in dev.
  command = ["server"]

  env = [
    "VAULT_LICENSE=${var.vault_license}",
    "VAULT_ADDR=http://127.0.0.1:8200",
  ]

  capabilities { add = ["IPC_LOCK"] }

  ports {
    internal = 8200
    external = var.vault_port
  }

  upload {
    file    = "/vault/config/vault.hcl"
    content = <<-HCL
      ui = false
      disable_mlock = true
      storage "raft" {
        path    = "/vault/data"
        node_id = "brieve-dev-vault-1"
      }
      listener "tcp" {
        address     = "0.0.0.0:8200"
        tls_disable = true
      }
      api_addr     = "http://127.0.0.1:8200"
      cluster_addr = "http://127.0.0.1:8201"
    HCL
  }

  healthcheck {
    # 501 = initialized but sealed; 200 = unsealed. Either means Vault is serving.
    test     = ["CMD-SHELL", "wget -qO- http://127.0.0.1:8200/v1/sys/health?sealedcode=200 || exit 1"]
    interval = "3s"
    retries  = 20
  }
}
