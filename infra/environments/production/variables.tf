# SPDX-License-Identifier: Apache-2.0
variable "vault_token" {
  description = "Bootstrap token for configuring the trust store. REVOKED once configuration is applied — ADR-0015's flow requires it, and this is the profile where it matters."
  type        = string
  sensitive   = true
}

variable "vault_address" {
  description = "Where the trust store answers. HTTPS."
  type        = string
}

variable "nomad_jwks_url" {
  type = string
}

variable "database_endpoint" {
  type = string
}

variable "agent_definitions" {
  type = map(object({
    description    = string
    owner          = string
    ceiling_policy = string
    allowed_paths  = list(string)
  }))
}
