# SPDX-License-Identifier: Apache-2.0
variable "vault_image" {
  description = "2.0.3+ent is a FLOOR, not a preference: the agent registry (ADR-0015) was introduced there."
  type        = string
  default     = "hashicorp/vault-enterprise:2.0.3-ent"
}

variable "vault_license" {
  type      = string
  sensitive = true
}

variable "vault_port" {
  type    = number
  default = 8200
}

variable "vault_node_id" {
  description = "Raft node id. Changing it against existing data strands the node outside its own peer set."
  type        = string
  default     = "brieve-dev-vault-1"
}

variable "tls_certificate" {
  description = "Listener certificate, issued by the control plane's CA. Empty means plaintext."
  type        = string
  default     = ""
}

variable "tls_private_key" {
  description = "Listener private key. Empty means plaintext."
  type        = string
  sensitive   = true
  default     = ""
}
