# SPDX-License-Identifier: Apache-2.0
#
# Operator-supplied. The production substrate describes an environment that already
# exists; it does not create one.

variable "vault_address" {
  description = "Where the trust store answers. HTTPS in production — see the TLS posture item."
  type        = string
}

variable "nomad_jwks_url" {
  description = "Scheduler JWKS, as reachable FROM the trust store."
  type        = string
}

variable "database_endpoint" {
  description = "host:port of the state store, as reachable FROM the trust store."
  type        = string
}
