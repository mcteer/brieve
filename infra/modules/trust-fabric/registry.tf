# SPDX-License-Identifier: Apache-2.0
#
# ADR-0015 calls the control-plane Vault "the agent registry and trust fabric". This is
# that feature — a first-class registry, not a convention implemented over kv.

resource "vault_identity_entity" "agent" {
  for_each = var.agent_definitions
  name     = each.key

  # THE ENTITY'S OWN CEILING, and the half that is invisible until a grant validates (016,
  # research F5).
  #
  # Vault's RAR evaluation is a restrictive intersection: a request must match a grant
  # constraint AND the entity's own ACL must permit it. An entity with empty `policies` is
  # therefore refused everything, whatever the grant says — which reads exactly like a broken
  # grant and is not one.
  #
  # The registration's `ceiling_policies` govern the agent-registry record; this governs the
  # ENTITY. The JWT-auth path in use before 016 never needed the second, which is why it was
  # empty and why nothing noticed. Both now name the same policy, because they are two
  # expressions of one ceiling and a divergence would be a ceiling that depended on which
  # door you came through.
  #
  # Set HERE rather than through `vault_identity_entity_policies`: that resource and this one
  # both manage the field, and with `exclusive = true` they fight — the entity resource wins
  # and reverts policies to empty, which was observed before this comment existed.
  policies = [each.value.ceiling_policy]
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

# WHAT MAKES A GRANT RESOLVABLE (016, research F5).
#
# A task-scoped grant names its subject in the JWT's `sub`. Vault resolves that to an Identity
# entity through an ALIAS, and without a correctly shaped one it refuses with `no alias found /
# error looking up entity` — a message that appears only in the server log while the caller
# sees a bare 403.
#
# THREE THINGS ABOUT THE SHAPE, each established by trying the alternative:
#
#   1. The accessor is the AGENT REGISTRY's — not the identity mount's, and not the
#      resource-server profile's `config_id`. All three were tried; only this one binds.
#   2. `external_id` and `issuer` are REQUIRED, not decorative. An alias carrying only
#      `name` + `mount_accessor` + `canonical_id` is created happily and then resolves
#      nothing: the grant is refused exactly as if no alias existed. Verified by building
#      that alias, watching every grant fail, and adding the two fields.
#   3. `name` and `mount_accessor` remain mandatory anyway — the endpoint refuses
#      `'id' or 'mount_accessor' and 'name' must be provided` when given only the OAuth
#      fields. They are additions to the classic pair, not a replacement for it.
#
# **Written through `vault_generic_endpoint` rather than `vault_identity_entity_alias`**, and
# that is forced rather than preferred: the typed resource in provider 4.8 exposes only
# `canonical_id`, `custom_metadata`, `id`, `mount_accessor`, `name`, and `namespace`. It
# cannot express `external_id` or `issuer`, so it cannot build an alias that works for this.
# When the provider grows those fields this should move back to the typed resource.
#
# Lives beside the registration because it is meaningless without one: an alias pointing at an
# entity with no agent-registry record resolves to an agent Vault has never heard of.
# `agent-registry` is a BUILT-IN Enterprise mount — mounted by default, with no `vault_mount`
# resource in this module to read an accessor from. So the accessor is read back from
# `sys/mounts` at plan time. `data` is a flat string map, which stringifies nested objects,
# hence `data_json` and a decode.
data "vault_generic_secret" "mounts" {
  path = "sys/mounts"
}

resource "vault_generic_endpoint" "agent_grant_subject_alias" {
  for_each = var.agent_definitions

  path                 = "identity/entity-alias"
  disable_read         = true
  disable_delete       = true
  ignore_absent_fields = true

  data_json = jsonencode({
    # The `sub` the issuer mints. Equal to the display name, so a grant is legible to a human
    # who knows the estate rather than only to one holding an entity UUID.
    name           = each.key
    external_id    = each.key
    canonical_id   = vault_identity_entity.agent[each.key].id
    mount_accessor = jsondecode(data.vault_generic_secret.mounts.data_json)["agent-registry/"].accessor
    issuer         = local.task_authority_issuer
  })

  depends_on = [vault_generic_endpoint.agent_registration]
}
