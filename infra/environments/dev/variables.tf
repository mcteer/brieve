# SPDX-License-Identifier: Apache-2.0
variable "vault_license" {
  type      = string
  sensitive = true
}

variable "vault_token" {
  description = "Bootstrap token for configuring the trust store. Retained in development deliberately — revoking it here breaks the re-apply loop, and an enclave nobody re-applies costs more safety than the token does on a workstation."
  type        = string
  sensitive   = true
}

variable "enable_tls" {
  description = "On by default. Development should exercise the same transport production uses; an opt-in security property is one most environments never opt into."
  type        = bool
  default     = true
}

variable "agent_definitions" {
  type = map(object({
    description    = string
    owner          = string
    ceiling_policy = string
    allowed_paths  = list(string)
  }))
  default = {
    "demo-agent" = {
      description    = "Reference registration proving the ADR-0015 registry flow"
      owner          = "platform"
      ceiling_policy = "agent-ceiling-demo"
      allowed_paths  = ["secret/data/demo/*"]
    }
  }
}

# Supplied by the second phase of bring-up, not by a human.
#
# The bootstrap circularity, made concrete: the trust store cannot start with a
# certificate from a CA that is not yet serving. So it starts plaintext, its PKI engine
# is configured, it issues its own listener certificate, and the substrate is applied
# again with that certificate in hand. `enclave-up` drives that; these variables are how
# the second pass carries the material in.
variable "tls_certificate" {
  type    = string
  default = ""
}

variable "tls_private_key" {
  type      = string
  sensitive = true
  default   = ""
}

variable "ca_cert_file" {
  description = "Control-plane CA the provider must trust once the listener is on TLS. Written by bring-up to .enclave/ca.pem; empty while plaintext."
  type        = string
  default     = ""
}
