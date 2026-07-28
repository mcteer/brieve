# SPDX-License-Identifier: Apache-2.0

# An agent's ceiling. Whatever a task requests, authority cannot exceed this.
resource "vault_policy" "agent_ceiling" {
  for_each = var.agent_definitions

  name = each.value.ceiling_policy
  policy = join("\n", [
    for p in each.value.allowed_paths :
    "path \"${p}\" { capabilities = [\"read\"] }"
  ])
}

# Database access belongs to the WORKLOAD identity, never to an agent ceiling.
#
# Backwards, this is serious: database access inside a definition's ceiling would let a
# model-chosen tool call reach the checkpoint store, which is the run's own record of
# what it has done. An agent able to rewrite that could erase the evidence of a step it
# took.
resource "vault_policy" "harness_database" {
  name   = "harness-database"
  policy = <<-HCL
    path "${vault_mount.database.path}/creds/${local.database_role_name}" {
      capabilities = ["read"]
    }
  HCL
}

# The evidence read path's credential, deliberately a SEPARATE policy from the one above
# rather than another path added to it.
#
# Separate because the two are held by different things for different reasons: the harness
# policy lets a run write its own record, and this one lets a reader read records back.
# Merging them would mean anything able to read evidence could also write it, which is the
# distinction the whole read path exists to draw — and it would be a one-line merge that
# looked like tidying.
resource "vault_policy" "evidence_database" {
  name   = "evidence-database"
  policy = <<-HCL
    path "${vault_mount.database.path}/creds/${local.evidence_role_name}" {
      capabilities = ["read"]
    }
  HCL
}
