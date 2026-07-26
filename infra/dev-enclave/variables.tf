# SPDX-License-Identifier: Apache-2.0
variable "vault_image" {
  description = "Vault Enterprise image. 2.0.3+ent is a FLOOR, not a preference: the agent registry (ADR-0015) was introduced there."
  type        = string
  default     = "hashicorp/vault-enterprise:2.0.3-ent"
}

variable "vault_license" {
  description = "Vault Enterprise license. Sourced from VAULT_ENT_LICENSE in the gitignored .env; never committed."
  type        = string
  sensitive   = true
}

variable "vault_token" {
  description = "Root token for configuring Vault. Dev bootstrap only."
  type        = string
  sensitive   = true
}

variable "vault_port" {
  type    = number
  default = 8200
}

variable "nomad_jwks_url" {
  description = "Nomad's JWKS endpoint as reachable FROM the Vault container. On Docker Desktop the host is host.docker.internal."
  type        = string
  default     = "http://host.docker.internal:4646/.well-known/jwks.json"
}

variable "postgres_host" {
  description = "Postgres as reachable FROM the Vault container. On Docker Desktop the host is host.docker.internal."
  type        = string
  default     = "host.docker.internal:5432"
}

variable "postgres_database" {
  type    = string
  default = "brieve"
}

variable "postgres_bootstrap_user" {
  description = "Account Vault's database engine connects as to create dynamic roles. Not used by the harness."
  type        = string
  default     = "brieve"
}

variable "postgres_bootstrap_password" {
  description = "Bootstrap only, and rotated out of this value on first apply. See database-creds.tf."
  type        = string
  sensitive   = true
  default     = "dev-only-not-a-secret"
}

variable "harness_job_id" {
  description = "Nomad job ID permitted to read dynamic database credentials. Bound as a JWT claim so the attestation is load-bearing rather than decorative."
  type        = string
  default     = "harness"
}

variable "agent_definitions" {
  description = "Agent definitions registered in Vault's agent registry, each with its ceiling policies (Principle IV)."
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
