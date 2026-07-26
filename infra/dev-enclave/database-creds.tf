# SPDX-License-Identifier: Apache-2.0
#
# TRUST FABRIC — substrate-independent, like vault-trust.tf. Intended to apply
# unchanged against a production Vault; only the connection URL is environmental.
#
# This is FR-017a made real: the harness never holds a database password. It
# authenticates to Vault with its Nomad workload identity and receives a
# credential Vault created moments earlier, which Postgres itself expires.
#
# The ordering consequence is worth understanding before debugging this: the
# harness cannot reach the database until it has an attested identity, so the
# database path runs THROUGH the attestation chain rather than beside it. A
# connection failure here may well be an identity failure one step earlier.

resource "vault_mount" "database" {
  path        = "database"
  type        = "database"
  description = "Dynamic Postgres credentials for the agent harness (FR-017a)"
}

resource "vault_database_secret_backend_connection" "postgres" {
  backend       = vault_mount.database.path
  name          = "brieve"
  allowed_roles = [vault_database_secret_backend_role.harness.name]

  postgresql {
    # Vault runs in a container and Postgres under Nomad on the host, so Vault
    # reaches it the same way it reaches Nomad's JWKS.
    connection_url = "postgresql://{{username}}:{{password}}@${var.postgres_host}/${var.postgres_database}?sslmode=disable"
    username       = var.postgres_bootstrap_user
    password       = var.postgres_bootstrap_password
  }

  # After rotate-root runs, only Vault knows this password. Terraform must not
  # try to put the bootstrap one back — that would undo the rotation on every
  # apply and quietly restore the standing credential this exists to remove.
  lifecycle {
    ignore_changes = [postgresql[0].password]
  }
}

# The dynamic role. Each request creates a distinct Postgres user that Postgres
# drops when the lease ends — not a shared account handed out repeatedly.
resource "vault_database_secret_backend_role" "harness" {
  backend = vault_mount.database.path
  name    = "harness"
  db_name = "brieve"

  creation_statements = [
    "CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}';",
    # Membership in the parent role is what makes the schema usable across credentials.
    # Without it, tables created under one dynamic user are unowned by the next, and
    # migrations fail with "must be owner of table" the moment a lease rolls over. The
    # provider does SET ROLE on connect so every object is owned by ${var.postgres_bootstrap_user}.
    "GRANT \"${var.postgres_bootstrap_user}\" TO \"{{name}}\";",
    "GRANT ALL PRIVILEGES ON DATABASE \"${var.postgres_database}\" TO \"{{name}}\";",
    "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO \"{{name}}\";",
    "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO \"{{name}}\";",
    "GRANT CREATE ON SCHEMA public TO \"{{name}}\";",
  ]

  revocation_statements = [
    "REASSIGN OWNED BY \"{{name}}\" TO \"${var.postgres_bootstrap_user}\";",
    "DROP OWNED BY \"{{name}}\";",
    "DROP ROLE IF EXISTS \"{{name}}\";",
  ]

  # Deliberately short. A run outliving its credential reconnects under a new
  # one; it does not hold a long-lived handle (ADR-0026).
  default_ttl = 3600
  max_ttl     = 86400
}

resource "vault_policy" "harness_database" {
  name = "harness-database"
  policy = <<-HCL
    path "${vault_mount.database.path}/creds/${vault_database_secret_backend_role.harness.name}" {
      capabilities = ["read"]
    }
  HCL
}

# The harness authenticates as ITSELF, distinct from any agent definition. Agent
# ceilings bound what a model-chosen tool call may reach; this bounds what the
# platform's own process may reach. Merging them would let an agent's ceiling
# widen or narrow the harness's database access, which are unrelated concerns.
resource "vault_jwt_auth_backend_role" "harness" {
  backend                 = vault_jwt_auth_backend.nomad.path
  role_name               = "harness"
  role_type               = "jwt"
  bound_audiences         = ["vault.io"]
  user_claim              = "/nomad_job_id"
  user_claim_json_pointer = true

  # Only the harness job may assume this role. Without the bound claim any
  # Nomad workload could read database credentials, which would make the
  # attestation decorative.
  bound_claims = {
    nomad_job_id = var.harness_job_id
  }

  token_policies = [vault_policy.harness_database.name]
  token_ttl      = 300
  token_type     = "service"
}

# Rotate the bootstrap password out of everyone's hands but Vault's. This runs
# once; the password Postgres holds afterwards exists in no file, no variable,
# and no Terraform state.
#
# The tradeoff is honest and worth knowing: destroying the Postgres volume resets
# the database to the bootstrap password while Vault still holds the rotated one,
# and the connection then fails until this is re-run. `make dev-reset` should do
# both together.
resource "vault_generic_endpoint" "rotate_root" {
  path                 = "${vault_mount.database.path}/rotate-root/${vault_database_secret_backend_connection.postgres.name}"
  disable_read         = true
  disable_delete       = true
  ignore_absent_fields = true
  data_json            = "{}"

  depends_on = [vault_database_secret_backend_role.harness]
}
