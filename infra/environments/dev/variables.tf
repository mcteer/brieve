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
    # The HARNESS-DOMAIN ceiling — a different jurisdiction from the two fields above
    # (ADR-0044). Those bound which secrets a run's token may read; these bound which
    # tools an agent may call. Neither is derivable from the other, which is why both
    # are authored rather than one being generated from the other.
    tool_names      = list(string)
    product_actions = list(string)
  }))
  default = {
    # The 006 registration proof. Its ceiling grants a path under a mount that DOES exist
    # as of 010 — before that it named `secret/data/demo/*` with no `secret/` mounted, so
    # every assertion against it passed whether enforcement worked or not.
    "demo-agent" = {
      description     = "Reference registration proving the ADR-0015 registry flow"
      owner           = "platform"
      ceiling_policy  = "agent-ceiling-demo"
      allowed_paths   = ["secret/data/demo/*"]
      tool_names      = ["echo"]
      product_actions = []
    }

    # THE FIXTURE THAT CAN FAIL. Two definitions with deliberately different ceilings,
    # because "the ceiling bounds authority" is only demonstrable against a ceiling that
    # excludes something a run would otherwise get. One definition cannot show that: every
    # assertion would hold under a fabric that ignored ceilings entirely.
    "planner-agent" = {
      description     = "Plans but never applies — the narrow half of the ceiling pair"
      owner           = "platform"
      ceiling_policy  = "agent-ceiling-planner"
      allowed_paths   = ["secret/data/planner/*"]
      tool_names      = ["echo", "plan"]
      product_actions = ["product.workspace.read"]
    }
    "applier-agent" = {
      description     = "Plans and applies — the wide half"
      owner           = "platform"
      ceiling_policy  = "agent-ceiling-applier"
      allowed_paths   = ["secret/data/applier/*"]
      tool_names      = ["echo", "plan", "apply"]
      product_actions = ["product.workspace.read", "product.workspace.write"]
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

variable "vault_host_network" {
  description = <<-DESC
    Run the trust store in the host network namespace (Linux Docker) rather than
    publishing a port (Docker Desktop). See the substrate module for why this is a
    substrate difference and not a change.
  DESC
  type        = bool
  default     = false
}

variable "role_bindings" {
  type = map(object({
    tool_names      = list(string)
    product_actions = list(string)
  }))
  default = {
    # The operator role: everything the reference agent can do, so an intersection with a
    # ceiling is bounded by the CEILING rather than by the person — which is the case the
    # ceiling rows need in order to be about ceilings at all.
    "operator" = {
      tool_names      = ["echo", "plan", "apply"]
      product_actions = ["product.workspace.read", "product.workspace.write"]
    }
    # Deliberately narrower, and the reason it exists: with only one role, "two users get
    # different authority" (SC-004) is untestable. A fixture that cannot fail is not a
    # fixture.
    "reader" = {
      tool_names      = ["echo", "plan"]
      product_actions = ["product.workspace.read"]
    }
  }
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
