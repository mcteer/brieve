# SPDX-License-Identifier: Apache-2.0
#
# Transport security for the control plane (FR-010).
#
# The bootstrap circularity, named rather than glossed: the first certificate cannot come
# from a PKI engine that is not yet serving. This is the same shape as ADR-0048's
# Vault-under-Nomad argument and takes the same resolution — something outside the loop
# goes first. The substrate starts Vault with a short-lived self-signed certificate; this
# engine then issues the real one, and the listener is switched as part of apply rather
# than as a follow-up someone forgets.

resource "vault_mount" "pki" {
  count = var.enable_tls ? 1 : 0

  path                      = "pki"
  type                      = "pki"
  description               = "Control-plane CA (ADR-0025)"
  default_lease_ttl_seconds = 3600
  max_lease_ttl_seconds     = 315360000 # 10y — the CA outlives what it issues
}

resource "vault_pki_secret_backend_root_cert" "control_plane" {
  count = var.enable_tls ? 1 : 0

  backend     = vault_mount.pki[0].path
  type        = "internal"
  common_name = "brieve control plane CA"
  ttl         = "315360000"
  key_type    = "rsa"
  key_bits    = 4096
}

resource "vault_pki_secret_backend_role" "control_plane" {
  count = var.enable_tls ? 1 : 0

  backend          = vault_mount.pki[0].path
  name             = "control-plane"
  allowed_domains  = ["brieve.internal", "localhost"]
  allow_subdomains = true
  allow_localhost  = true
  allow_ip_sans    = true
  max_ttl          = "8760h"

  depends_on = [vault_pki_secret_backend_root_cert.control_plane]
}
