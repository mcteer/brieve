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

# Reading the harness-domain jurisdiction. READ ONLY, and deliberately its own policy.
#
# Not merged into `harness_database`: that policy exists so a run can write its own
# record, and merging would mean anything able to reach the state store could also read
# every ceiling in the estate. The evidence read path drew exactly this separation for
# exactly this reason, and the argument has not changed.
#
# No write capability appears here at all. These records are written by Terraform from
# reviewed HCL (ADR-0015's division of labor: definitions in HCL, enforcement in Vault),
# because writing a wider ceiling record IS widening a scope — the deliberate, reviewable
# act ADR-0016 governs. Nothing at runtime writes them, and nothing at runtime should be
# able to.
resource "vault_policy" "harness_authority_read" {
  name   = "harness-authority-read"
  policy = <<-HCL
    path "${vault_mount.harness_authority.path}/data/harness-ceilings/*" {
      capabilities = ["read"]
    }
    path "${vault_mount.harness_authority.path}/data/role-bindings/*" {
      capabilities = ["read"]
    }
    # Policy narrows a definition mid-run, and is read on EVERY step (FR-008). Granted
    # even though no deployment writes one yet: without the capability Vault answers 403
    # rather than 404, so "no policy record" is indistinguishable from "not allowed to
    # look" — and the fabric would report an unreachable trust fabric for a definition
    # that simply has no policy, suspending runs that should have proceeded unrestricted.
    path "${vault_mount.harness_authority.path}/data/policies/*" {
      capabilities = ["read"]
    }
    path "agent-registry/registration/display-name/*" {
      capabilities = ["read"]
    }
  HCL
}
