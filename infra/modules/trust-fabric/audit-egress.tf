# SPDX-License-Identifier: Apache-2.0
#
# The platform's credential at the second copy, rotated by Vault and known to nobody.
#
# 015 first shipped this as a hand-written password stored at a KV path — a standing
# credential, argued for at length on the grounds that registering the collector in this
# Vault would mean seeding the collector's ROOT here and handing the platform's
# administrators the destination's credential lifecycle. The premise is sound. The
# conclusion was wrong, because root seeding is not the only way to register a database.
#
# ROOTLESS. `self_managed = true` means this connection holds no privileged account on the
# collector at all: Vault connects AS `harness_shipper` and rotates that account's own
# password. The maximum privilege obtainable here — by this module, by an operator holding
# the root token, by anyone who compromises this Vault entirely — is `INSERT` and `SELECT`
# on two tables, because that is everything the connection's own identity has. Seeding the
# collector's root would instead have let whoever controls this Vault define a role granting
# `UPDATE` on `shipped_entries`, which is precisely the tampering ADR-0055 exists to make
# impossible. Rootless is not the convenient option; it is the one that survives the threat
# model this feature was built for.
#
# WHY THIS LIVES IN trust-fabric. An earlier note argued the collector's roles belong outside
# this module because the platform does not administer that store. Onboarding is a different
# act from administering: nothing here grants a privilege, defines a role, or touches a
# table. It records a credential the collector's operator already issued, and asks Vault to
# keep rotating it. The collector's operator revokes by altering the grants or dropping the
# role, and neither is reachable from here.
#
# THE SEED IS MEANT TO BE WORTHLESS. `self_managed_password` is the bootstrap value the
# collector's operator hands over once. Vault rotates it on import — `skip_import_rotation`
# is deliberately left at its default — so the value written in configuration stops working
# immediately and the password in force afterwards is known to nothing but Vault. That is
# the same shape `rotate-root` gives the state store, and it is why a bootstrap credential
# in a variable is not a standing credential.

resource "vault_database_secret_backend_connection" "collector" {
  backend       = vault_mount.database.path
  name          = local.collector_connection_name
  allowed_roles = [local.collector_role_name]

  # There is no root credential to verify against, and nothing to verify: the connection's
  # own identity is the static role's, which Vault is about to rotate.
  verify_connection = false

  postgresql {
    self_managed = true
    # No username/password. Under a rootless connection Vault opens a dedicated connection
    # per static role using that role's own credential, which is the whole mechanism.
    connection_url = "postgresql://{{username}}:{{password}}@${var.collector_endpoint}/${var.collector_database}?sslmode=disable"
  }
}

resource "vault_database_secret_backend_static_role" "audit_shipper" {
  backend  = vault_mount.database.path
  name     = local.collector_role_name
  db_name  = vault_database_secret_backend_connection.collector.name
  username = var.collector_shipper_username

  # Handed over once by the collector's operator, and dead on arrival: Vault rotates on
  # import. See the header — this variable's value is not a secret worth protecting after
  # the first apply, which is exactly the property that makes seeding acceptable.
  self_managed_password = var.collector_shipper_bootstrap_password

  # Daily. The shipper reads the current value from `database/static-creds/` on each pass it
  # builds a destination, so rotation is invisible to it and needs no restart, no reload,
  # and no human.
  rotation_period = 86400
}
