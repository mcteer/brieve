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
    # The HARNESS-DOMAIN ceiling — a different jurisdiction from the two fields above
    # (ADR-0044). Those bound which secrets a run's token may read; these bound which
    # tools an agent may call. Neither is derivable from the other, which is why both
    # are authored rather than one being generated from the other.
    tool_names      = list(string)
    product_actions = list(string)
    # 013. Declared here as well as in the module: Terraform's object-type conversion
    # silently DROPS attributes the type does not name, and the first apply of vault-agent
    # wrote packs = [] for exactly that reason — the values were in the tfvars map and the
    # root variable's type threw them away without a warning.
    packs       = optional(list(string), [])
    binding_map = optional(map(string), {})
    tier        = optional(number, 1)
  }))
}

variable "ca_cert_file" {
  description = "Control-plane CA the provider must trust. Operator-supplied in production."
  type        = string
}

variable "role_bindings" {
  description = <<-DESC
    What a claim-derived role means in the harness domain.

    The same jurisdiction as an agent's ceiling — both answer "what may this principal
    call" — so the same store, the same governance, and the same reader. A person's role
    and an agent's definition meet as peers in Principle IV's intersection, and giving
    them different homes would suggest they are different kinds of thing.
  DESC
  type = map(object({
    tool_names      = list(string)
    product_actions = list(string)
  }))
  default = {}
}

variable "definition_policies" {
  description = <<-DESC
    Policy narrowing a definition below its ceiling, keyed by agent definition id.

    Empty is the normal state. A policy is how an operator tightens a definition without
    editing its ceiling — for an incident or a migration — and it is read on every step so
    the narrowing takes effect on the next one rather than at the next run.
  DESC
  type = map(object({
    tool_names      = list(string)
    product_actions = list(string)
  }))
  default = {}
}
