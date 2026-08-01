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

# Which packs a definition reaches, which model it uses per role, and what it may compose.
#
# **The record the whole of 013 reads.** FR-005's isolation consumes `packs`, binding-map
# validation consumes `binding_map`, and tier resolution consumes `tier` — and until analyze
# pass 8 these three fields lived in the glossary, in four tasks' logic, and in no record at
# all. Every consumer had been written against something nothing produced.
#
# BESIDE THE CEILING, NOT ON THE REGISTRATION, for the reason recorded at the top of this
# file: the registry engine's `register` endpoint takes a closed parameter set with no
# extension point. Same store, same jurisdiction, same governance.
#
# Written by the SAME apply as the ceiling, for the reason the ceiling records: two applies
# leave a window where a definition has one and not the other. That window is fail-closed —
# a missing binding record refuses — but it would present as an outage with no cause.
#
# `for_each` over the same variable, so a definition cannot acquire a ceiling without
# acquiring bindings. Defaults are the narrowest thing that still runs: no packs, no
# bindings, tier 1 (paved paths only). A definition that names no pack is exactly what
# 008-012's fixtures are, and they must keep working unchanged.
resource "vault_kv_secret_v2" "definition_bindings" {
  for_each = var.agent_definitions

  mount = vault_mount.harness_authority.path
  name  = "definition-bindings/${each.key}"

  data_json = jsonencode({
    schema_version      = 1
    agent_definition_id = each.key
    packs               = each.value.packs
    binding_map         = each.value.binding_map
    tier                = each.value.tier
  })
}

# The Qualified Model Matrix — which models evaluation has qualified, per pack and role.
#
# **Authored here for the first time in 020**, and its absence until now is the finding.
# 013 built the reader (`core.authority.matrix`), the policy grant, and the run-start
# validation; nothing ever wrote the record, so `_resolve_binding_map` returned before
# touching it for every definition — because every definition bound nothing. The matrix and
# its binding maps were correct, complete, and load-bearing for nothing.
#
# ONE RECORD, not one per cell. `read_matrix()` reads a single path and parses the whole
# vocabulary, because validating a binding map means asking "is this cell qualified" against
# the *set* — a per-cell layout would make an absent cell and an unreachable store the same
# 404, which is the distinction `MatrixSource` exists to preserve.
#
# Read-only to runs. A run that could write a cell could qualify a model for itself, which is
# eval-gated promotion (Principle VIII) with the gate on the inside.
resource "vault_kv_secret_v2" "model_matrix" {
  mount = vault_mount.harness_authority.path
  name  = "model-matrix"

  data_json = jsonencode({
    schema_version = 1
    cells          = var.model_matrix_cells
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

# Per-definition policy, which narrows a ceiling without changing it.
#
# Empty by default and that is the expected state: policy exists to tighten a definition
# temporarily — an incident, a migration, a product being drained — and most definitions
# most of the time have none. The absence of a record means unrestricted, which the fabric
# reads as `None` rather than as a failure.
resource "vault_kv_secret_v2" "definition_policy" {
  for_each = var.definition_policies

  mount = vault_mount.harness_authority.path
  name  = "policies/${each.key}"

  data_json = jsonencode({
    schema_version  = 1
    tool_names      = each.value.tool_names
    product_actions = each.value.product_actions
  })
}
