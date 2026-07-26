# SPDX-License-Identifier: Apache-2.0
#
# SUBSTRATE — the only layer permitted to differ between environments (ADR-0025).
#
# The trust store is NOT scheduled here, and that is the point. Two independent reasons
# (ADR-0048): containment — the identity record must not live in the substrate whose
# access control it exists to constrain — and circularity, since the scheduler is itself
# a client of the store, so that arrangement has no cold start that terminates.
#
# The constraint is SCHEDULING, not packaging. Running the trust store as a container
# this substrate creates directly is correct; submitting it as a scheduler job is not.

terraform {
  required_providers {
    docker = { source = "kreuzwerker/docker", version = "~> 3.0" }
  }
}

resource "docker_image" "vault" {
  name         = var.vault_image
  keep_locally = true
}

resource "docker_volume" "vault_data" {
  name = "brieve-dev-vault-data"
}

# A fresh named volume is owned by root; the trust store runs as uid 100. Without this
# it crash-loops on "permission denied" opening its own bolt file, and nothing in that
# message points at ownership.
#
# A provisioner rather than a one-shot container: a container that removes itself leaves
# Terraform holding an id that no longer resolves, and one that does not is permanent
# cruft in `docker ps -a`.
resource "terraform_data" "vault_data_chown" {
  triggers_replace = [docker_volume.vault_data.id]

  provisioner "local-exec" {
    command = "docker run --rm --user root -v ${docker_volume.vault_data.name}:/vault/data --entrypoint chown ${var.vault_image} -R 100:1000 /vault/data"
  }
}

resource "docker_container" "vault" {
  name    = "brieve-dev-vault"
  image   = docker_image.vault.image_id
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

  # "CAP_IPC_LOCK", not "IPC_LOCK". Docker normalises the name on read, so the short
  # form is a permanent diff — and because capability changes force replacement, every
  # apply would recreate the container and RESEAL the trust store. It presents as a
  # race and is not one.
  capabilities { add = ["CAP_IPC_LOCK"] }

  ports {
    internal = 8200
    external = var.vault_port
  }

  upload {
    file = "/vault/config/vault.hcl"
    # node_id is load-bearing. Raft data is bound to it: move a store to a differently
    # named node and it unseals, reports standby forever, and answers every API call
    # "Vault is sealed". Nothing connects the two.
    content = <<-CFG
      ui = false
      disable_mlock = true
      storage "raft" {
        path    = "/vault/data"
        node_id = "${var.vault_node_id}"
      }
      listener "tcp" {
        address     = "0.0.0.0:8200"
        tls_disable = true
      }
      api_addr     = "http://127.0.0.1:8200"
      cluster_addr = "http://127.0.0.1:8201"
    CFG
  }

  healthcheck {
    # 501 = initialised but sealed; 200 = unsealed. Either means it is serving.
    test     = ["CMD-SHELL", "wget -qO- http://127.0.0.1:8200/v1/sys/health?sealedcode=200 || exit 1"]
    interval = "3s"
    retries  = 20
  }
}
