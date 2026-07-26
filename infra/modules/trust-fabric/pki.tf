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

  backend = vault_mount.pki[0].path
  name    = "control-plane"
  # host.docker.internal is how workloads in other containers reach the trust store, so
  # a certificate without it fails verification for every one of them — while working
  # perfectly from the operator's shell, which is the confusing half.
  allowed_domains  = ["brieve.internal", "localhost", "host.docker.internal"]
  allow_subdomains = true
  # Without this, listing a domain permits only its SUBDOMAINS — "host.docker.internal"
  # itself is refused while "*.host.docker.internal" is fine. The error says the name is
  # "not allowed by this role" even though the role lists it, which sends you looking at
  # the wrong field.
  allow_bare_domains = true
  allow_localhost    = true
  allow_ip_sans      = true
  # Seconds, not "8760h". Vault normalises durations to seconds on read, so the string
  # form never matches what comes back and every plan shows an in-place update forever —
  # the same perpetual-diff shape as writing IPC_LOCK in short form.
  max_ttl = 31536000 # 1 year

  depends_on = [vault_pki_secret_backend_root_cert.control_plane]
}

# The trust store's own listener certificate.
#
# Issued BY the control plane's CA, which is what makes this the control plane's own
# transport rather than a certificate from somewhere else that happens to work.
#
# The CA's private key never leaves Vault (type = "internal"). This certificate's key
# does pass through Terraform state, and that is a real and narrower exposure worth
# naming: it is one server certificate, rotatable, in a local gitignored state file —
# not the CA. Avoiding even that would need a CSR generated inside the container, which
# Terraform cannot express.
resource "vault_pki_secret_backend_cert" "listener" {
  count = var.enable_tls ? 1 : 0

  backend     = vault_mount.pki[0].path
  name        = vault_pki_secret_backend_role.control_plane[0].name
  common_name = "localhost"
  ip_sans     = ["127.0.0.1"]
  alt_names   = ["localhost", "host.docker.internal"]
  ttl         = "8760h"

  # Reissue before expiry rather than after. A listener certificate that expires takes
  # the whole control plane offline, and the failure names TLS rather than the clock.
  auto_renew            = true
  min_seconds_remaining = 2592000 # 30 days
}
