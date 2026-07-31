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
# How the shipper reaches the SECOND copy (015, ADR-0055).
#
# One path, read-only, and every part of that is deliberate.
#
# **What it grants is a ROTATING credential, not a stored one.** `database/static-creds/`
# returns whatever password Vault most recently set on `harness_shipper`; nobody wrote it
# and nobody knows it. 015 first pointed this policy at a KV path holding a hand-written
# password, which made the platform's Vault a place credentials are *kept* rather than
# *managed* — see `audit-egress.tf` for why that was unnecessary.
#
# **Why the platform's Vault holds it at all**, when the whole feature is about the platform
# not administering the destination: the connection behind it is rootless, so this Vault's
# maximum reach at the collector is the shipper's own `INSERT`/`SELECT`. The collector's
# operator revokes by altering the grants or dropping the role, neither of which is
# reachable from here.
#
# **Why not the jobspec's env block**, which is where the plan first put it: the credential
# carries SELECT on `shipped_entries`, which is the entire evidence copy across every
# tenant. Jobspec metadata is readable by anyone with scheduler access, so delivering it
# there would create an ungoverned evidence read sitting beside ADR-0035's governed one —
# the same exposure that keeps a person's free text out of `run_inputs`, arriving by a
# different door. The COORDINATES do travel that way, and they are not the credential.
#
# The credential itself is append+read at the destination and can alter nothing already
# shipped; `probe()` demonstrates that on every reconcile pass rather than trusting it.
resource "vault_policy" "audit_egress_credential" {
  name   = "audit-egress-credential"
  policy = <<-HCL
    path "${vault_mount.database.path}/static-creds/${local.collector_role_name}" {
      capabilities = ["read"]
    }
  HCL
}

resource "vault_policy" "agent_pack_secrets" {
  name   = "agent-pack-secrets"
  policy = <<-HCL
    path "${vault_mount.agent_secrets.path}/data/conformance/*" {
      capabilities = ["read"]
    }
    path "${vault_mount.agent_secrets.path}/metadata/*" {
      capabilities = ["read"]
    }
    # NO WRITE CAPABILITY, and 014 checked before concluding that.
    #
    # FR-006a needs an interrupted `vault_write` resolved by observation against the real
    # product, both directions, which reads as though a dispatched run must be able to write
    # here. It does not. `surfaces.handlers.vault_write` is a STUB: it validates its
    # arguments, requires `cas`, and returns `{"written": True}` without touching Vault. What
    # is real is the OBSERVER, which reads `metadata/{idempotency_key}` — covered by the read
    # grant above.
    #
    # So the live re-observation rows arrange the external state from the HOST, with an
    # operator token, and the dispatched run only has to leave an open intent behind. A write
    # grant added here would have been a standing capability for every dispatched run, bought
    # to satisfy a requirement that turned out not to need it — which is worth recording,
    # because the reasoning that asks for it is entirely plausible right up to reading the
    # handler.
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
    # Claim-to-role mappings, written under Control Group by the submit endpoint and
    # read back here to build the token verifier. Read AND list, because KV v2 splits
    # them: without `list` on the metadata path the surface can read a mapping it
    # already knows the name of and can discover none, which resolves every token to no
    # roles — indistinguishable, from the caller's side, from a correctly empty estate.
    #
    # Still no write. The surface REQUESTS a mapping change through the gated path and
    # the Control Group decides; a surface that could write its own mappings could grant
    # itself a role, which is the escalation ADR-0016 closes.
    path "${vault_mount.harness_authority.path}/data/claim-mappings/*" {
      capabilities = ["read"]
    }
    path "${vault_mount.harness_authority.path}/metadata/claim-mappings" {
      capabilities = ["list"]
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
