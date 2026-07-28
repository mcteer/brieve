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

variable "vault_host_network" {
  description = <<-DESC
    Run the trust store in the HOST network namespace instead of publishing a port.

    A substrate difference, and the only permitted kind (Principle VII). Docker Desktop
    provides `host.docker.internal`, so a bridged trust store reaches the state store by
    name. Linux Docker provides no such name, and `host-gateway` only helps if the state
    store's published port is bound to the bridge address — Nomad binds it to one
    interface, and on a Linux runner that is loopback. The trust store then resolves the
    host correctly and gets "connection refused", which reads as a database problem.

    Host networking sidesteps the whole question: both processes share the host's
    namespace and reach each other at 127.0.0.1. It is wrong for Docker Desktop, where the
    namespace is the VM's and the port would stop being reachable from macOS at all —
    which is why this is a variable and not a change.
  DESC
  type        = bool
  default     = false
}
