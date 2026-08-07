# SPDX-License-Identifier: Apache-2.0
#
# THE PRINCIPAL THE REQUEST-AND-DECIDE MECHANISM NEVER HAD (044, ADR-0069).
#
# `authority_submit.py` has shipped since 007: it posts a change to the trust fabric and maps
# Vault's three native outcomes — queued for approval, applied, denied. The surface requests;
# the Control Group decides. Correct, conformance-covered, and **never once exercisable in a
# deployment**, because measured on merged main:
#
#   - no policy in this module grants `create` or `update` on ANY `harness-authority` path
#   - `vault_policy.authority_change` — the Control-Group-gated write policy — is attached to
#     no role at all
#   - `VaultAuthoritySubmitter` is constructed in `service.py` with no token
#
# The gated rows pass because they run with an operator token. This is 041's shape one layer
# down: correct, tested, wired to nothing. 044's first job is not a settings page — it is
# giving the mechanism a principal.
#
# **The API's own attested identity, not a configured token.** A token in the jobspec would be
# a standing credential (Principle IV); a dedicated console identity would be a second thing to
# bound for no gain, since the API already authenticates the person originating the request.
# The person is bounded at the role-gated route; this grant is bounded to the records the
# console may write; the Control Group decides. Three bounds, none of them a credential.

# What the console may write, and nothing else.
#
# **Three records, enumerated rather than globbed.** A glob over `harness-authority/data/*`
# would hand the console `harness-ceilings` and `model-matrix` — the records that decide what
# agents may do and which models are qualified — and those are estate governance this feature
# deliberately leaves in Terraform (spec Assumptions). An enumeration is also what makes
# `test_console_controlled_paths.py`'s completeness scan possible: a set you can compare.
#
# `claim-mappings/*` is a glob because it is one record per mapping — 007 found that writing
# every mapping to the configured path itself meant the second approved mapping overwrote the
# first, so granting one person a role revoked someone else's.
resource "vault_policy" "authority_submit" {
  name   = "authority-submit"
  policy = <<-HCL
    # Claim-to-role mappings. The path 007's submitter already writes, and the one whose
    # gating this module asserted and never attached (analyze FR-023 — established, and
    # fixed by the `controlled_paths` extension in control-groups.tf).
    path "${vault_mount.harness_authority.path}/data/claim-mappings/*" {
      capabilities = ["create", "update"]
    }

    # The ask binding: which qualified cell answers, which judges, and 044's relevance
    # toggle. Writable here because binding a QUALIFIED cell is a choice about which
    # permitted model to use — the matrix still decides what is permitted, and the console
    # refuses a cell the matrix does not carry before the fabric is ever asked.
    path "${vault_mount.harness_authority.path}/data/ask-bindings" {
      capabilities = ["create", "update"]
    }

    # Product connections (044). Locations only — an address, an organisation, a namespace.
    # The material used to authenticate to a product stays in the trust store and is
    # referenced; there is no field here a credential could be written into.
    path "${vault_mount.harness_authority.path}/data/product-connections" {
      capabilities = ["create", "update"]
    }
  HCL
}

# The Control Group on those same paths, when a quorum is configured.
#
# **Separate from `authority_change`** rather than added to it: that policy is built from
# `controlled_paths` for the Vault-native surfaces (ceilings, auth roles, the registry,
# identity entities), and its own comment records that our deployment tree is subject to it.
# The console's records are harness-domain KV, and merging them would mean a change to one
# jurisdiction's gate silently altering the other's.
#
# **When `control_groups_enabled` is false there is no gate, and that is the development
# posture** — legitimate, and the console is required to SAY so (FR-007/023b) rather than let
# an ungated apply read as an approval that happened.
resource "vault_policy" "authority_submit_gated" {
  count = local.control_groups_enabled ? 1 : 0

  name = "authority-submit-gated"
  policy = join("\n", [
    for p in local.console_controlled_paths : <<-POLICY
      path "${p}" {
        capabilities = ["create", "update"]
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
