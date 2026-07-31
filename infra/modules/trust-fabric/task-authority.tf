# SPDX-License-Identifier: Apache-2.0
#
# The issuer that mints task-scoped authority, and the trust Vault places in it (016,
# ADR-0056).
#
# Principle IV describes authority as manufactured per task — "attested workload identity →
# control-plane Vault → RFC 8693 + RAR against ceiling policies". Until this feature the
# `task scope` term of that intersection had nothing behind it: a run's token carried the
# agent definition's whole ceiling for the whole run.
#
# **Vault is the RESOURCE SERVER here, not the authorization server**, and that distinction
# is the one ADR-0056 had to establish by reading the binary rather than the marketing.
# Vault's own OIDC provider accepts `authorization_code` and nothing else, so it cannot
# perform the exchange. What it does is validate a JWT some trusted issuer minted, resolve
# the subject to an Identity entity, and evaluate the RAR details against that entity's
# ceiling — which is exactly the half we needed and could not have written ourselves.

resource "vault_mount" "task_authority" {
  path        = "task-authority"
  type        = "transit"
  description = "Signs task-scoped authority grants (016). The key never leaves Vault."
}

# ECDSA P-256, and NOT a free choice.
#
# `transit/sign` marshals signatures as ASN.1 by default, which JWS cannot read. The `jws`
# marshaling that produces a usable ES256 signature is documented as "currently only valid
# for ECDSA P-256 key types", so the algorithm follows from the mechanism rather than from a
# preference. Recorded because a future reader will otherwise wonder why this is not Ed25519.
resource "vault_transit_secret_backend_key" "grant_issuer" {
  backend = vault_mount.task_authority.path
  name    = "grant-issuer"
  type    = "ecdsa-p256"

  # The public half is registered with the resource-server profile below, so Vault can
  # verify what this key signs. Exporting the PRIVATE half is never enabled: the whole
  # argument for transit over a PKI-issued certificate is that no private key material
  # exists outside this mount — not in the issuing service, not on its disk, not in memory.
  exportable             = false
  allow_plaintext_backup = false
}

# WHO MAY MINT AUTHORITY, and this is the feature's new privilege.
#
# ADR-0056's Notes name it and FR-020 requires it be bounded: whoever can call `sign` on this
# key can manufacture task scope for any agent. That makes this policy as load-bearing as the
# ceiling records themselves — it is the ceiling's *issuer*.
#
# Bounded to one path on one key. Not `transit/*`, not the mount, and deliberately not
# `transit/verify` either: verification is Vault's job during validation, and a workload with
# no reason to verify has no reason to hold the capability.
resource "vault_policy" "task_authority_sign" {
  name   = "task-authority-sign"
  policy = <<-HCL
    path "${vault_mount.task_authority.path}/sign/${vault_transit_secret_backend_key.grant_issuer.name}" {
      capabilities = ["update"]
    }
  HCL
}

locals {
  # `issuer_id` and `sub` are matched literally by Vault, so both live here rather than being
  # spelled out at each use. The URL is an identifier, not an address — nothing resolves it,
  # and nothing should try.
  task_authority_issuer = "https://harness.internal/task-authority"
  grant_issuer_key_id   = "grant-issuer-1"

  # Read off the resource rather than hardcoded, so rotating the key does not mean editing
  # this file. A stale PEM here would fail closed in the most confusing way available: every
  # grant refused with a bare 403 whose reason exists only in Vault's server log.
  #
  # `keys` is a list of version maps; version 1 is the only one until a rotation, and a
  # rotation is a deliberate act that revisits this line. There is no data source for transit
  # public keys in provider 4.x — the resource's computed attribute is the whole of it.
  grant_issuer_pem = vault_transit_secret_backend_key.grant_issuer.keys[0]["public_key"]
}

# The trust: Vault will honour grants signed by the key above.
#
# THREE THINGS HERE COST AN HOUR EACH TO DISCOVER (research F2/F4), so they are written down
# rather than left for the next person:
#
#   1. `use_jwks` defaults to TRUE. Omitting it fails with "jwks_uri is required when
#      use_jwks=true" even when `public_keys` is supplied. It must be set false explicitly.
#   2. `public_keys` entries must be JSON OBJECTS. The Vault CLI's key=value form fails with
#      "public_key at index 0 must be an object"; `vault_generic_endpoint` sends JSON, so the
#      trap does not bite here — but it will bite anyone reproducing this by hand.
#   3. `optional_authorization_details` stays FALSE (its default), which makes RAR details
#      MANDATORY on this path. A grant without them is refused. That is the fail-closed
#      direction: a token that forgot to say what it was for gets nothing.
#
# Static keys rather than a JWKS URI, and that is a deliberate simplification: the issuer
# serves no discovery document and no JWKS endpoint, so there is no public surface to
# operate, secure, or keep available. Terraform places the key beside the profile that trusts
# it, which is one fewer moving part than the design originally assumed it needed.
resource "vault_generic_endpoint" "task_authority_resource_server" {
  path                 = "sys/config/oauth-resource-server/task-authority"
  disable_read         = true
  disable_delete       = false
  ignore_absent_fields = true

  data_json = jsonencode({
    issuer_id = local.task_authority_issuer
    audiences = ["vault"]
    jwt_type  = "access_token"
    use_jwks  = false
    public_keys = [{
      key_id = local.grant_issuer_key_id
      pem    = local.grant_issuer_pem
    }]
  })
}
