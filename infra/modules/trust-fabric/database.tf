# SPDX-License-Identifier: Apache-2.0
#
# FR-017a of 005, made real: the harness holds no database password. It authenticates
# with its workload identity and receives a credential Vault minted moments earlier.
#
# The ordering consequence is worth knowing before debugging anything here: the harness
# cannot reach the database until it has an attested identity, so the database path runs
# THROUGH the attestation chain rather than beside it. A connection failure is often an
# identity failure one step earlier.

resource "vault_mount" "database" {
  path        = "database"
  type        = "database"
  description = "Dynamic state-store credentials for the harness"
}

locals {
  # Literal on both sides: referencing the role from the connection and the connection
  # from the role is a dependency cycle Terraform rejects.
  database_connection_name = "brieve"
  database_role_name       = "harness"
}

resource "vault_database_secret_backend_connection" "state_store" {
  backend       = vault_mount.database.path
  name          = local.database_connection_name
  allowed_roles = [local.database_role_name]

  postgresql {
    connection_url = "postgresql://{{username}}:{{password}}@${var.database_endpoint}/${var.database_name}?sslmode=disable"
    username       = var.database_bootstrap_user
    password       = var.database_bootstrap_password
  }

  # After rotate-root, only Vault knows this password. Terraform must not put the
  # bootstrap one back — that would undo the rotation on every apply and quietly
  # restore the standing credential the rotation exists to remove.
  lifecycle {
    ignore_changes = [postgresql[0].password]
  }
}

resource "vault_database_secret_backend_role" "harness" {
  backend = vault_mount.database.path
  name    = local.database_role_name
  db_name = vault_database_secret_backend_connection.state_store.name

  creation_statements = [
    "CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}';",
    # Membership in the parent role is what makes the schema usable across credentials.
    # Without it, objects created under one dynamic user are unowned by the next, and
    # migrations fail with "must be owner of table" the moment a lease rolls over.
    "GRANT \"${var.database_bootstrap_user}\" TO \"{{name}}\";",
    "GRANT ALL PRIVILEGES ON DATABASE \"${var.database_name}\" TO \"{{name}}\";",
    "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO \"{{name}}\";",
    "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO \"{{name}}\";",
    "GRANT CREATE ON SCHEMA public TO \"{{name}}\";",
  ]

  revocation_statements = [
    "REASSIGN OWNED BY \"{{name}}\" TO \"${var.database_bootstrap_user}\";",
    "DROP OWNED BY \"{{name}}\";",
    "DROP ROLE IF EXISTS \"{{name}}\";",
  ]

  default_ttl = 3600
  max_ttl     = 86400
}

# Puts the bootstrap password beyond everyone's reach but Vault's.
#
# The coupling this creates is real and bites in both directions: destroy the state
# store's volume and it reverts to the bootstrap password while Vault holds the rotated
# one; disable this mount and Vault forgets the rotated password while the store still
# has it. Either way nothing can authenticate. They reset together — see the failure
# catalogue in infra/README.md.
resource "vault_generic_endpoint" "rotate_root" {
  path                 = "${vault_mount.database.path}/rotate-root/${local.database_connection_name}"
  disable_read         = true
  disable_delete       = true
  ignore_absent_fields = true
  data_json            = "{}"

  depends_on = [vault_database_secret_backend_role.harness]
}
