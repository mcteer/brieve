# SPDX-License-Identifier: Apache-2.0
#
# ADR-0015 calls the control-plane Vault "the agent registry and trust fabric". This is
# that feature — a first-class registry, not a convention implemented over kv.

resource "vault_identity_entity" "agent" {
  for_each = var.agent_definitions
  name     = each.key
}

resource "vault_generic_endpoint" "agent_registration" {
  for_each = var.agent_definitions

  path                 = "agent-registry/register"
  disable_read         = true
  disable_delete       = true
  ignore_absent_fields = true

  data_json = jsonencode({
    display_name     = each.key
    entity_id        = vault_identity_entity.agent[each.key].id
    description      = each.value.description
    owner            = each.value.owner
    ceiling_policies = [each.value.ceiling_policy]
  })

  depends_on = [vault_policy.agent_ceiling]
}
