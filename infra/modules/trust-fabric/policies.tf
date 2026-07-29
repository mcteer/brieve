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

# What a dispatched run's PACK TOOLS may read in the agent secret space (013).
#
# Role-level, and the limitation is the point of the comment: every dispatched run shares
# this grant, because narrowing the VAULT-TOKEN layer per definition is credential
# translation (ADR-0044) — its own feature, explicitly out of 013's scope. What IS
# per-definition today is the harness-domain ceiling: which TOOLS a definition may call is
# bounded by its ceiling record, and a definition whose ceiling omits `vault_read` never
# reaches this path at all. The two jurisdictions stay disjoint (ADR-0044), and this grant
# is the fixture space the conformance probe reads — not a production posture.
resource "vault_policy" "agent_pack_secrets" {
  name   = "agent-pack-secrets"
  policy = <<-HCL
    path "${vault_mount.agent_secrets.path}/data/conformance/*" {
      capabilities = ["read"]
    }
    path "${vault_mount.agent_secrets.path}/metadata/*" {
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
    # The Qualified Model Matrix (013, ADR-0022/0039). Read at every run start when a
    # binding map is resolved, and read-only to runs for the same reason ceilings are:
    # a run that could write a cell could qualify a model for itself.
    #
    # The 403-not-404 trap above applies exactly, and worse. Without this grant the matrix
    # is unreadable AND the failure presents as an unreachable trust fabric, so whoever
    # debugs it goes to Vault's health rather than to a missing policy line — for a matrix
    # that merely lacks a grant. Analyze pass 1 found this as the feature's first CRITICAL;
    # the block above is where the same trap was already written down.
    path "${vault_mount.harness_authority.path}/data/model-matrix/*" {
      capabilities = ["read"]
    }
    # Which packs a definition reaches, its binding map, and its tier (013). The record the
    # whole feature reads: isolation, binding-map validation, and tier resolution all
    # consume these three fields. Beside the ceiling and granted in the same policy,
    # because a definition holding one and not the other is a definition nothing can
    # resolve.
    path "${vault_mount.harness_authority.path}/data/definition-bindings/*" {
      capabilities = ["read"]
    }
    path "agent-registry/registration/display-name/*" {
      capabilities = ["read", "list"]
    }
    # LIST on the folder itself, because enumeration asks "what definitions exist" and the
    # glob above answers only "what is at this name". 010 granted exactly what resolution
    # needed — resolution knows the id it wants — and enumeration is the second caller,
    # which is the seam pattern in policy form.
    path "agent-registry/registration/display-name" {
      capabilities = ["list"]
    }
  HCL
}
