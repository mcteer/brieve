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
  evidence_role_name       = "evidence"
  # 015. The second copy, onboarded rootless — see `audit-egress.tf`.
  collector_connection_name = "collector"
  collector_role_name       = "audit-shipper"
}

resource "vault_database_secret_backend_connection" "state_store" {
  backend       = vault_mount.database.path
  name          = local.database_connection_name
  allowed_roles = [local.database_role_name, local.evidence_role_name]

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

# The evidence read path's role. SELECT on audit_entries, and nothing else, anywhere.
#
# This is defence #2 of the two that keep the audit read path incapable of mutation
# (ADR-0035, specs/008-northbound-api). Defence #1 is that `EvidenceQuery` names no write
# method — which holds only while application code is correct, and is the one a future
# refactor removes by handing the read path a writable connection. This one holds
# regardless of what the Python does, because Postgres refuses the write.
#
# Three deliberate narrownesses, each of which would be easy to widen by accident:
#
#   1. `audit_entries` by name, NOT `ON ALL TABLES IN SCHEMA public` as the harness role
#      above uses. All-tables would also hand the evidence path durability's checkpoints,
#      which is wider than anything the read path is supposed to see.
#   2. No grant on `audit_stream_heads` at all — not even SELECT. The heads are what make
#      truncation detectable, so the read path must not be able to learn what it would
#      need to forge.
#   3. No membership in the parent role. Membership is what makes the harness role able to
#      own and alter objects; granting it here would quietly undo the whole point.
#
# The task list called for ALTER DEFAULT PRIVILEGES so later tables would not escape the
# grant. That is the wrong instrument HERE, and the conflict is worth recording rather
# than resolving silently: default privileges apply to every future table in the schema,
# which would hand this role `audit_stream_heads` the moment that table is created — the
# exact grant narrowness #2 exists to withhold. A convenience that re-grants the one thing
# you deliberately withheld is not a convenience.
#
# Instead the grants are explicit and re-evaluated on every credential issuance, so they
# are always current for the tables named. Adding a readable evidence table is then a
# deliberate edit here rather than something that happens by default, and enclave-verify
# asserts both halves: the role CAN read audit_entries and CANNOT read the heads.
resource "vault_database_secret_backend_role" "evidence" {
  backend = vault_mount.database.path
  name    = local.evidence_role_name
  db_name = vault_database_secret_backend_connection.state_store.name

  creation_statements = [
    "CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}';",
    "GRANT CONNECT ON DATABASE \"${var.database_name}\" TO \"{{name}}\";",
    "GRANT USAGE ON SCHEMA public TO \"{{name}}\";",
    "GRANT SELECT ON audit_entries TO \"{{name}}\";",
    # Not dependency_health, and not suspended_runs. Neither is evidence — both are
    # operational state that happens to share a database — and widening a SELECT-only
    # credential to cover "things in the same database" is exactly how it stops being a
    # narrow credential and becomes a general reader.
    # Belt and braces. The role was never granted this and inherits nothing, but the
    # table is the one thing whose exposure would defeat truncation detection, so the
    # withholding is stated rather than left implied.
    "REVOKE ALL PRIVILEGES ON audit_stream_heads FROM \"{{name}}\";",
    "REVOKE ALL PRIVILEGES ON dependency_health FROM \"{{name}}\";",
    "REVOKE ALL PRIVILEGES ON suspended_runs FROM \"{{name}}\";",
    # Same treatment, same reason (011). A run index says who started what and an
    # authority-change record says who asked for which privilege — both are operational
    # state that happens to share a database, and a SELECT-only credential able to read
    # every run's starter across the estate has stopped being a narrow credential.
    "REVOKE ALL PRIVILEGES ON run_index FROM \"{{name}}\";",
    "REVOKE ALL PRIVILEGES ON authority_change_requests FROM \"{{name}}\";",
    # And the grant store (014). Same treatment, same reason, and the sharpest case yet: a
    # grant record says which human consented to which definition doing what, across every
    # tenant. It is consent metadata rather than evidence — the trail records what a run DID,
    # this table records what it was ALLOWED to do — and a SELECT-only credential able to read
    # every subject's consent estate-wide has stopped being a narrow credential by exactly the
    # argument that withheld `run_index`.
    #
    # Belt and braces like the others: the role is granted `audit_entries` and nothing else,
    # and inherits nothing, so it never had this. Stated because a withholding nobody wrote
    # down is a withholding the next `ON ALL TABLES` convenience undoes.
    "REVOKE ALL PRIVILEGES ON grants FROM \"{{name}}\";",
  ]

  revocation_statements = [
    "REVOKE ALL PRIVILEGES ON audit_entries FROM \"{{name}}\";",
    "REVOKE ALL PRIVILEGES ON DATABASE \"${var.database_name}\" FROM \"{{name}}\";",
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
