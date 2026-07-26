# SPDX-License-Identifier: Apache-2.0
#
# Production posture (FR-010). Each item is implemented or deferred WITH A REASON —
# silence is the failure this requirement exists to prevent, not deferral.

# ---------------------------------------------------------------- bootstrap credential
#
# ADR-0015's flow revokes the bootstrap token once configuration is applied, after which
# every caller authenticates through the attestation chain.
#
# Development deliberately does NOT. Revoking it there breaks the re-apply loop that
# makes the enclave usable day to day, and an enclave nobody re-applies costs more safety
# than the retained token does on a workstation. That is a PROFILE difference, not a
# substrate one — which is why it lives here and not in a substrate module.
resource "vault_generic_endpoint" "revoke_bootstrap_token" {
  count = var.profile == "production" ? 1 : 0

  path                 = "auth/token/revoke-self"
  disable_read         = true
  disable_delete       = true
  ignore_absent_fields = true
  data_json            = "{}"

  # Last. Everything this token is needed for must already exist — revoking it partway
  # through leaves a half-configured control plane and no way to finish.
  depends_on = [
    vault_jwt_auth_backend_role.agent,
    vault_jwt_auth_backend_role.harness,
    vault_jwt_auth_backend_role.conformance,
    vault_generic_endpoint.agent_registration,
    vault_generic_endpoint.rotate_root,
    vault_pki_secret_backend_role.control_plane,
  ]
}

# ---------------------------------------------------------------------------- posture
#
# Machine-readable so the "each item has a disposition" check is an assertion rather than
# someone reading prose. FR-010 is satisfied by the PRESENCE of a disposition; which
# disposition is a planning decision.
locals {
  production_posture = {
    transport_security = {
      # Precise on purpose. The CA is implemented and issues; switching the trust
      # store's own LISTENER to TLS is the remaining step, and it is not declarative:
      # the first certificate cannot come from a PKI that is not yet serving, so it goes
      # plaintext -> configure PKI -> issue -> restart with TLS. Claiming "implemented"
      # for the whole item would be the silent-absence failure wearing a better word.
      disposition = var.enable_tls ? "ca-implemented-listener-pending" : "disabled-in-this-environment"
      detail      = "The control plane's own CA is created and issues certificates for the control-plane role. Switching the trust store's listener to TLS requires a bootstrap sequence (start plaintext, configure PKI, issue, restart) and every client's address and CA trust to move with it; until that lands, transport is plaintext on loopback."
    }
    bootstrap_credential = {
      disposition = var.profile == "production" ? "implemented" : "retained-deliberately"
      detail      = "Revoked after configuration under the production profile. Retained in development: revoking it there breaks the re-apply loop, and an enclave nobody re-applies costs more safety than the token does on a workstation."
    }
    unseal_shape = {
      disposition = var.seal_config == null ? "seam-only" : "operator-supplied"
      detail      = "seal_config passes an auto-unseal configuration through untouched. Shipping one KMS variant would privilege a cloud and still leave every other operator writing their own."
    }
    high_availability = {
      disposition = "deferred"
      detail      = "The only one of the four unverifiable without multi-node infrastructure this project does not have. A tree claiming HA that has never survived a node loss is worse than one that says it is single-node. Trigger: the first deployment target that requires it, or the first time single-node behaviour is suspected of hiding a fencing defect. CONSEQUENCE: 005's conformance caveat persists — fencing and parking are proven against single-node behaviour only."
    }
  }
}

# FR-010 as a hard failure rather than a review item.
resource "terraform_data" "posture_dispositions" {
  input = local.production_posture

  lifecycle {
    precondition {
      condition = alltrue([
        for item in values(local.production_posture) :
        item.disposition != "" && item.detail != ""
      ])
      error_message = "every production posture item needs a disposition and a reason; silence is the failure FR-010 exists to prevent, deferral is not."
    }
  }
}
