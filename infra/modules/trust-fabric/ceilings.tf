# SPDX-License-Identifier: Apache-2.0
#
# The HARNESS-DOMAIN jurisdiction: what an agent definition may call, and what a role means.
#
# Separate from the ceiling policies in policies.tf, and the separation is the decision
# rather than an implementation detail. ADR-0044: "policy jurisdictions are disjoint... no
# rule is duplicated across engines." A ceiling policy bounds which SECRETS a run's token
# may read; these records bound which TOOLS an agent may call and what a role's holder may
# delegate. They are about different things, so neither may be derived from the other —
# and a reader that inferred one from the other would turn a secrets grant into a tool
# grant without anyone deciding it should.
#
# WHY KV RATHER THAN THE AGENT REGISTRY. The registry is a first-class Vault Enterprise
# engine (`agent_registry`) whose `register` endpoint takes a closed parameter set:
# ceiling_policies, description, display_name, entity_id, id, owner,
# no_default_ceiling_policy, optional_authorization_details. There is no extension point,
# so the harness ceiling cannot live on the registration however much it would like to.
#
# `registry.tf` says the registry is "a first-class registry, not a convention implemented
# over kv", and that comment is right about what it addresses: reimplementing VAULT's
# concept over KV when Vault ships the engine. The harness-domain ceiling is OUR concept,
# for which no engine exists. Storing our data in their store is glue; rebuilding their
# product would not be.

resource "vault_mount" "harness_authority" {
  path        = "harness-authority"
  type        = "kv"
  options     = { version = "2" }
  description = "Harness-domain ceilings and role bindings (ADR-0044 tool-authorization jurisdiction)"
}

# One record per agent definition, keyed by the same display name the registration uses.
#
# Written by the SAME apply as the registration. Two applies would leave a window in which
# a registered agent has no ceiling — which refuses, so the window is fail-closed rather
# than open, but it would present as an outage with no cause. One apply, no window.
resource "vault_kv_secret_v2" "harness_ceiling" {
  for_each = var.agent_definitions

  mount = vault_mount.harness_authority.path
  name  = "harness-ceilings/${each.key}"

  data_json = jsonencode({
    schema_version      = 1
    agent_definition_id = each.key
    tool_names          = each.value.tool_names
    product_actions     = each.value.product_actions
  })
}

# What a claim-derived role means in the harness domain.
#
# Same store and same governance as the ceilings above, because it is the same
# jurisdiction: both answer "what may this principal call", one for an agent definition
# and one for a person. The intersection in Principle IV consumes them as peers.
resource "vault_kv_secret_v2" "role_binding" {
  for_each = var.role_bindings

  mount = vault_mount.harness_authority.path
  name  = "role-bindings/${each.key}"

  data_json = jsonencode({
    schema_version  = 1
    role            = each.key
    tool_names      = each.value.tool_names
    product_actions = each.value.product_actions
  })
}

# The mount the reference ceiling policies grant against.
#
# Before 010 there was none: `agent-ceiling-demo` granted `secret/data/demo/*` and
# `secret/` was not mounted, so the reference ceiling granted access to nothing. Harmless
# for a registration-flow proof, which is all 006 claimed — and useless as a fixture for a
# feature about ceilings bounding things, because every assertion against it would pass
# whether enforcement worked or not.
resource "vault_mount" "agent_secrets" {
  path        = "secret"
  type        = "kv"
  options     = { version = "2" }
  description = "Per-agent secret space the ceiling policies bound access to"
}
