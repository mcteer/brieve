# SPDX-License-Identifier: Apache-2.0
#
# The development claim mapping that lets a browser sign-in reach the platform.
#
# The dev identity provider mints `permissions=["platform:operator"]` by default, and
# every served surface reads mappings from the trust store. Without a record here, sign-in
# succeeds and the first API call answers `403 unmapped_claim` — indistinguishable from a
# broken deployment to whoever is using the portal.
#
# Seeded in development only, with no Control Group in that profile, so the write is
# immediate. Production estates approve mappings through quorum (ADR-0016); this must never
# be enabled there.

locals {
  dev_operator_claim_mapping = {
    claim_name  = "permissions"
    claim_value = "platform:operator"
    role        = "operator"
  }
  # Must match `core.identity.mappings_store.mapping_key` for these three fields
  # (NUL-joined SHA-256, first sixteen hex digits). Written as a literal because
  # Terraform 1.15 rejects `\x00` in quoted strings, and a different separator
  # would seed a record the verifier never reads.
  dev_operator_mapping_key = "operator-55ad4f49e3f06147"
}

resource "vault_kv_secret_v2" "dev_operator_claim_mapping" {
  count = var.seed_dev_claim_mapping ? 1 : 0

  mount = vault_mount.harness_authority.path
  name  = "claim-mappings/${local.dev_operator_mapping_key}"

  data_json = jsonencode({
    claim_name   = local.dev_operator_claim_mapping.claim_name
    claim_value  = local.dev_operator_claim_mapping.claim_value
    role         = local.dev_operator_claim_mapping.role
    requested_by = "enclave-bootstrap"
  })

  # SEED ONCE, THEN LEAVE THE RECORD ALONE. An operator who revokes or replaces this mapping
  # through the console must not have the next apply revert their decision.
  lifecycle {
    ignore_changes = [data_json]
  }
}

variable "seed_dev_claim_mapping" {
  description = <<-DESC
    Seed the dev-provider claim mapping (`permissions: platform:operator` -> `operator`).
    Dev only — production approves mappings through the Control Group, and enabling this
    there would bypass that gate.
  DESC
  type        = bool
  default     = false
}
