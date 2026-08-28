# SPDX-License-Identifier: Apache-2.0
#
# THE MEASUREMENT NAMESPACE (042, ADR-0068).
#
# Vault has no plan-equivalent for a policy as a whole. `terraform plan` answers "what would
# happen"; a Vault policy answers nothing until something holds it. So the impact of a
# PROPOSED policy is measured by writing it under a throwaway name, minting a token carrying
# only it, asking Vault's own `sys/capabilities` what that token could do, and destroying
# both — inside one tool call, with destruction in a `finally`.
#
# **The product answers. The platform never infers.** A derived answer — diffing HCL,
# reasoning about capabilities — would be the fixture problem wearing better clothes, and
# ADR-0047 is what this feature exists to avoid repeating.
#
# **Everything here is bounded by `scratch-agent-*` and that bound is the product's.** Even
# with every check in this repository removed, the ACL below admits nothing else. That is
# the third of three independent layers (request validation, the governance hook, this), and
# the only one that survives a platform bug.

# What a dispatched run may do in the measurement namespace, and nothing beyond it.
#
# A SEPARATE POLICY rather than lines added to `agent_pack_secrets`, on the reasoning
# `evidence_database` already carries: two grants held for different reasons should be
# revocable independently. Withdrawing policy authoring should not require deciding what
# else a run loses.
#
# **No attach capability, and V20 scans for its absence.** Nothing here reaches `identity/*`,
# `auth/<mount>/role/*`, or `auth/token/roles/*`, so FR-021's "never attached to any entity,
# role, or auth mount" rests on a grant that cannot express attachment — not on the impact
# handler happening not to try. A row asserts that, because a later edit adding an attach
# path would break the guarantee silently and read as a widening of scope rather than a
# defeat of the safety case.
resource "vault_policy" "scratch_policy_check" {
  name   = "scratch-policy-check"
  policy = <<-HCL
    # The measurement namespace. `create` and `update` for the same reason `vault_write`
    # needs both: writing a policy is a create when there is none and an update when there
    # is, and a grant naming one fails on whichever case arrives first.
    #
    # `delete` is what makes the `finally` block work. `read` is what lets a row assert the
    # policy is gone rather than assuming it.
    # 054: THE RUN'S OWN WORKSPACE, AND NOTHING ELSE.
    #
    # This was `scratch-agent-*` — estate-wide, granted to every dispatched run, while the
    # names it protects were already per-run. Demonstrated 2026-08-27: a token carrying
    # exactly what this role grants read (200), overwrote (200) and deleted (204) another
    # run's measurement policy.
    #
    # **Terraform cannot write the narrow form directly**, which is why the wildcard was not
    # laziness: an allocation id does not exist at apply time. The template is evaluated by
    # Vault, per request, against the caller's OWN attested identity — so the platform never
    # derives this scope, never stores it, and cannot widen it. A wider grant is not refused
    # here; it is unrepresentable.
    #
    # The alias name is the allocation id because `auth.tf` sets `user_claim` to it. Change
    # one without the other and every run is refused its own workspace — which row E4 exists
    # to catch, since refusing everything satisfies the refusal rows while breaking the
    # product.
    path "sys/policies/acl/scratch-agent-{{identity.entity.aliases.${vault_jwt_auth_backend.workload.accessor}.name}}-*" {
      capabilities = ["create", "update", "delete", "read"]
    }

    # Minting the subject of the measurement, THROUGH A ROLE.
    #
    # A bare `auth/token/create` can only grant policies the parent already holds, so using
    # one would mean attaching the scratch policy to the run's own token — a run holding
    # authority over what bounds it, in miniature, which is exactly what Principle IV makes
    # structurally unavailable. The role carries the `allowed_policies_glob`, so the bound
    # belongs to Vault rather than to the caller's good behaviour.
    path "auth/token/create/scratch-check" {
      capabilities = ["update"]
    }

    # Asking the question. `sys/capabilities` takes the subject token in the BODY and is
    # called by the platform — `capabilities-self` would have to be called by the scratch
    # token, which is minted `no_default_policy` and therefore cannot reach it. Restoring
    # `default` to make that possible would mean the token no longer carries only the policy
    # under measurement, and the answer would describe the union.
    path "sys/capabilities" {
      capabilities = ["update"]
    }
  HCL
}

# The token role that bounds what a scratch token may carry.
#
# `allowed_policies_glob` is the whole safety argument at the product level: a run may ask
# for any policy it likes and Vault will refuse anything outside the measurement namespace.
# V16 asserts this **with the platform's governance hook disabled**, because a back-stop that
# is only ever exercised behind a working front-stop has never been tested.
resource "vault_token_auth_backend_role" "scratch_check" {
  role_name = "scratch-check"

  allowed_policies_glob = ["scratch-agent-*"]

  # `orphan = false` keeps the minted token a child of the run's own, so revoking the run's
  # token revokes the measurement's. An orphan would outlive its reason to exist.
  orphan = false

  # Sixty seconds. Long enough for a handful of capability queries against a local Vault,
  # short enough that a run killed mid-measurement leaves no usable credential behind —
  # which is why FR-023's sweep is about orphaned POLICIES and not about tokens.
  token_period           = 0
  token_explicit_max_ttl = 60
  renewable              = false
  token_type             = "service"
  disallowed_policies    = ["default"]
}

# The sweep's grant, held by the persistent service and by nothing else.
#
# `list` over the whole policy namespace is genuinely more than a run should have — it
# enumerates every policy name in the estate, which is why it lives here and not on
# `agent-run`. The service needs it because finding an ORPHAN means finding a name nobody
# told you about; a sweep that could only look up names it already knew would find nothing.
#
# Delete is bounded to the measurement namespace even here. A sweeper able to delete
# arbitrary policies would be a bigger standing capability than the thing it cleans up.
resource "vault_policy" "scratch_sweep" {
  name   = "scratch-sweep"
  policy = <<-HCL
    path "sys/policies/acl" {
      capabilities = ["list"]
    }
    path "sys/policies/acl/scratch-agent-*" {
      capabilities = ["read", "delete"]
    }
  HCL
}

# THE PROTECTED SET, PUBLISHED BY THE MODULE THAT DECLARES IT.
#
# FR-006 says the set is derived, never a hand-maintained list that drifts the first time a
# policy is added. Terraform cannot reflect over its own resources, so the derivation is
# split: this list is written by hand, and **V6 scans `infra/modules/trust-fabric/*.tf` for
# every `resource "vault_policy"` declaration and fails the merge when one is missing**. The
# list is hand-written; the completeness is mechanical.
#
# **The runtime alternative was measured and rejected.** "Every live policy minus the scratch
# namespace" reads as more automatic and is wrong here: in this enclave every live policy IS
# a trust-fabric policy, so the derivation would protect everything, US1 could read nothing,
# and the safety rows would pass by making the feature unusable. In a customer estate the
# same rule would protect every application policy from the agent — the defect's mirror
# image.
#
# `scratch_policy_check` is in the list. It bounds the measurement namespace, so a run able
# to author it could widen its own reach.
resource "vault_kv_secret_v2" "protected_policies" {
  mount = vault_mount.harness_authority.path
  name  = "protected-policies"

  data_json = jsonencode({
    schema_version = 1
    # `concat` with a splat, because `authority_change` is COUNT-GATED on control groups
    # being enabled. `vault_policy.authority_change[*].name` is a one-element list when the
    # policy exists and an empty one when it does not — so the published set describes the
    # estate that was actually applied rather than the one the module can express.
    #
    # Referencing it as `.name` fails to plan outright, which is how this was found: a
    # count-gated resource has no singular attribute. Worth recording because the same shape
    # will bite the next policy that arrives behind a feature flag.
    names = sort(concat([
      vault_policy.agent_pack_secrets.name,
      vault_policy.audit_egress_credential.name,
      vault_policy.authoring_publisher.name,
      vault_policy.evidence_database.name,
      vault_policy.harness_authority_read.name,
      vault_policy.harness_database.name,
      vault_policy.model_credential_read.name,
      vault_policy.scratch_policy_check.name,
      vault_policy.scratch_sweep.name,
      # 044. `authority_submit` is the console's own write grant — a run able to rewrite it
      # could widen what the console may change, and from there reach the records this whole
      # safety case protects. Caught by V6 at the moment the policy was declared, which is
      # what that scan is for.
      vault_policy.authority_submit.name,
      ],
      # ONE CEILING POLICY PER AGENT DEFINITION — `agent_ceiling` is `for_each` over
      # `var.agent_definitions`, so this is N policies, not one. Every one of them is
      # exactly what Principle IV means by "what bounds the agent": a run able to author
      # its own ceiling is the escalation the whole feature exists to make unavailable.
      #
      # `values(...)` rather than a singular reference, for the same reason `authority_change`
      # needs a splat. Both were found by `terraform validate` refusing to plan, and both
      # would have published a set that silently omitted the most important names in it.
      values(vault_policy.agent_ceiling)[*].name,
      vault_policy.authority_change[*].name,
      # Count-gated on the quorum, like `authority_change` above and for the same reason.
      vault_policy.authority_submit_gated[*].name,
    ))
  })
}
