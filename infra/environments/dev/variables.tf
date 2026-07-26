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
  description = "Opt-in in development; always on in production."
  type        = bool
  default     = false
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
