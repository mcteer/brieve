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

# Raft data outlives the container. Without this, every recreate produces a fresh
# uninitialised Vault — which reads as "the trust configuration vanished" and cost
# an afternoon to diagnose once already.
resource "docker_volume" "vault_data" {
  name = "brieve-dev-vault-data"
}

# A fresh named volume is owned by root, and Vault runs as uid 100 — so without
# this the server crash-loops on `permission denied` opening its own bolt file,
# with nothing in the message pointing at ownership.
#
# Deliberately a provisioner rather than a `docker_container`: a one-shot
# container either removes itself, leaving Terraform holding an ID that no
# longer resolves, or lingers in Exited state as permanent cruft. Neither is
# worth it for a chown. Tied to the volume so it re-runs if the volume is
# recreated, and not otherwise.
resource "terraform_data" "vault_data_chown" {
  triggers_replace = [docker_volume.vault_data.id]

  provisioner "local-exec" {
    command = "docker run --rm --user root -v ${docker_volume.vault_data.name}:/vault/data --entrypoint chown ${var.vault_image} -R 100:1000 /vault/data"
  }
}

resource "docker_container" "vault" {
  name  = "brieve-dev-vault"
  image = docker_image.vault.image_id
  # Enterprise rejects "inmem" storage outright, so raft is required even in dev.
  command = ["server"]
  restart = "unless-stopped"

  depends_on = [terraform_data.vault_data_chown]

  volumes {
    volume_name    = docker_volume.vault_data.name
    container_path = "/vault/data"
  }

  env = [
    "VAULT_LICENSE=${var.vault_license}",
    "VAULT_ADDR=http://127.0.0.1:8200",
  ]

  # "CAP_IPC_LOCK", not "IPC_LOCK". Docker normalizes the name on read, so the
  # short form produces a permanent diff — and since capability changes force
  # replacement, every apply would recreate the container and reseal Vault.
  capabilities { add = ["CAP_IPC_LOCK"] }

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
