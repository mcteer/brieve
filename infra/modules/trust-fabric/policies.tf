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
