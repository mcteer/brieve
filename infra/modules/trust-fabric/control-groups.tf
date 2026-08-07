# SPDX-License-Identifier: Apache-2.0
#
# QUORUM ON AUTHORITY CHANGES (ADR-0016).
#
# > Hooks gate what agents DO. Control Groups gate what agents may BECOME.
#
# TWO MECHANISMS, DELIBERATELY. Both were established by testing against the running
# enclave rather than from documentation, and the difference between them is the whole
# design:
#
#   1. An ACL `control_group` stanza on each policy granting a gated path. A write then
#      returns a WRAPPING TOKEN rather than succeeding — a pending approval request. This
#      is where "blocked pending approval" comes from, and it is native: Vault already
#      distinguishes it from denial, so we do not have to invent the distinction.
#
#   2. A Sentinel EGP as a BACKSTOP. The control_group stanza lives in a policy, so the
#      gate is only as complete as the set of policies granting those paths — a new policy
#      granting the same path without the stanza would bypass it entirely. The EGP is
#      path-attached and catches that case. It denies rather than queues, which is the
#      correct outcome for a path someone granted without a gate.
#
# ROOT BYPASSES BOTH. Verified: a root token wrote to a gated path with no approval and no
# denial. That is not a flaw to work around — it is why the production profile revokes the
# bootstrap credential. Revoking it is not hygiene; it is what makes this gate real.
#
# What this file does NOT do:
#   - Gate REVOCATION. Unilateral and immediate, deliberately. A control making revocation
#     as slow as granting is one people route around in an incident.
#   - Gate BREAK-GLASS. Root regeneration requires a quorum of unseal-share holders — a
#     `sys` operation outside normal policy paths that neither mechanism can intercept, and
#     already a stronger multi-party control.
#   - Touch RUNS. An agent mid-run holds authority already granted.

locals {
  control_groups_enabled = var.quorum_policy != null

  # Attach to PATHS. A gate on callers is a gate on the callers someone thought of.
  #
  # The uncomfortable consequence: our own deployment tree is subject to this once the
  # policy is in force. Provisioning applies it before the bootstrap credential is revoked,
  # which is the only reason the bootstrap terminates.
  controlled_paths = [
    "sys/policies/acl/agent-ceiling-*",
    "${vault_jwt_auth_backend.workload.path}/role/*",
    "agent-registry/register",
    "identity/entity/*",
    "sys/policies/acl/authority-change-*",
  ]

  # 044: the harness-domain records the admin console may write.
  #
  # **A separate list, deliberately.** `controlled_paths` above gates the Vault-native
  # surfaces and its own comment notes that our deployment tree is subject to it; these are
  # KV records in the harness jurisdiction. Merging them would mean a change to one gate
  # silently altering the other's blast radius.
  #
  # **This closes a gap the module asserted and never attached** (044 FR-023, established
  # rather than assumed): `authority_controlled_path` defaults to
  # `harness-authority/data/claim-mappings` and its description calls that "the
  # Control-Group-gated path", while nothing in `controlled_paths` covered it. The submitter
  # has requested changes on an ungated path since 007 — visible only because the console
  # made the gating load-bearing.
  console_controlled_paths = [
    "${vault_mount.harness_authority.path}/data/claim-mappings/*",
    "${vault_mount.harness_authority.path}/data/ask-bindings",
    "${vault_mount.harness_authority.path}/data/product-connections",
    "${vault_mount.harness_authority.path}/data/endorsed-sources",
  ]
}

# The approver set. Membership is the customer's Vault administrator's to manage.
resource "vault_identity_group" "authority_approvers" {
  count = local.control_groups_enabled ? 1 : 0

  name = "authority-approvers"
  type = "internal"
}

# Mechanism 1 — the approval workflow.
#
# A caller holding this policy gets a wrapping token instead of a write. That token is the
# pending request; unwrapping it after quorum performs the change.
resource "vault_policy" "authority_change" {
  count = local.control_groups_enabled ? 1 : 0

  name = "authority-change-gated"
  policy = join("\n", [
    for p in local.controlled_paths : <<-POLICY
      path "${p}" {
        capabilities = ["create", "update", "delete"]
        control_group = {
          factor "approvers" {
            identity {
              group_names = ["${vault_identity_group.authority_approvers[0].name}"]
              approvals   = ${var.quorum_policy.required_approvals}
            }
          }
        }
      }
    POLICY
  ])
}

# Mechanism 2 — the backstop.
#
# Catches a path granted by some OTHER policy that carries no control_group stanza. Without
# this, adding such a policy silently removes the gate, and nothing would report it.
resource "vault_egp_policy" "authority_change_backstop" {
  count = local.control_groups_enabled ? 1 : 0

  name              = "authority-change-backstop"
  paths             = local.controlled_paths
  enforcement_level = "hard-mandatory"

  policy = <<-SENTINEL
    # A write reaching a controlled path WITHOUT a control-group authorization has come
    # through a policy that lacks the stanza. Deny — the correct outcome for a path
    # someone granted without a gate.
    #
    # hard-mandatory: no timeout grants by default, no escalation lowers the bar (FR-009).
    #
    # The requester's own endorsement never counts (FR-008); otherwise the requirement is
    # one person with two hats.
    requester_excluded = rule {
      not (request.entity.id in controlgroup.authorizations)
    }

    quorum_met = rule {
      length(controlgroup.authorizations) >= ${var.quorum_policy.required_approvals}
    }

    main = rule { quorum_met and requester_excluded }
  SENTINEL
}
