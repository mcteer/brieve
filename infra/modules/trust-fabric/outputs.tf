# SPDX-License-Identifier: Apache-2.0
#
# NO OUTPUT CARRIES CREDENTIAL MATERIAL. A module output is the easiest place for one to
# escape into a root's state file, which is on disk and not always gitignored by
# whoever copied the tree.

output "jwt_auth_path" {
  value       = vault_jwt_auth_backend.workload.path
  description = "Mount a workload authenticates against: POST /v1/auth/<path>/login"
}

output "database_creds_path" {
  value       = "${vault_mount.database.path}/creds/${local.database_role_name}"
  description = "Where a workload reads a dynamic credential, having first authenticated as itself."
}

output "registered_agents" {
  value       = keys(var.agent_definitions)
  description = "Agent definitions present in the registry."
}

output "ca_certificate" {
  value       = var.enable_tls ? vault_pki_secret_backend_root_cert.control_plane[0].certificate : ""
  description = "Control-plane CA, for clients that must trust it. Public material, not a secret."
}

# ---------------------------------------------------------------- the SC-001 evidence
#
# Delegated to a provider-free module so the comparison can run offline. Duplicating the
# computation here would let the two drift, and the one that drifted would be the one
# nobody ran.

module "digest" {
  source = "../configuration-digest"

  agent_definitions  = var.agent_definitions
  harness_job_id     = var.harness_job_id
  conformance_job_id = var.conformance_job_id
  enable_tls         = var.enable_tls
}

output "configuration_digest" {
  value       = module.digest.digest
  description = "Stable hash of every configured element. Identical across substrates, or FR-002 is false."
}

output "configuration_elements" {
  value       = module.digest.elements
  description = "The digest's inputs, so a mismatch can be diffed rather than merely reported."
}

output "production_posture" {
  value       = local.production_posture
  description = "Each of the four items with its disposition and reason. Deferral is acceptable; silence is not (FR-010)."
}

# Listener material, consumed by the substrate to switch its own transport on.
#
# Sensitive: the private key is here. Marked so it cannot land in a log by accident —
# `terraform output` refuses to print it without -raw, and CI log scrapers skip it.
output "listener_certificate" {
  value       = var.enable_tls ? vault_pki_secret_backend_cert.listener[0].certificate : ""
  description = "Control-plane listener certificate, issued by the control plane's own CA."
}

output "listener_private_key" {
  value       = var.enable_tls ? vault_pki_secret_backend_cert.listener[0].private_key : ""
  sensitive   = true
  description = "Listener private key. One rotatable server key — not the CA, which never leaves the trust store."
}

output "listener_ca_chain" {
  value       = var.enable_tls ? vault_pki_secret_backend_cert.listener[0].issuing_ca : ""
  description = "Issuing CA, for clients that must trust this listener."
}

output "evidence_credentials_path" {
  description = "Vault path issuing the SELECT-only evidence credentials (008, FR-009)."
  value       = "${vault_mount.database.path}/creds/${local.evidence_role_name}"
}
