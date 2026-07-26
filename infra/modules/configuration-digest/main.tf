# SPDX-License-Identifier: Apache-2.0
#
# The SC-001 evidence, in a module with NO PROVIDERS.
#
# Extracted here for one reason: the comparison must be computable without a live trust
# store. If the digest could only be read from an applied root, checking the feature's
# central claim would require both environments to exist — which means it would never be
# checked, and SC-001 would be decorative.
#
# Computed from resolved inputs and literal configuration only. Substrate-derived values
# are excluded on purpose: including an address would make the digests differ by
# construction and the comparison worthless.

locals {
  configuration_elements = {
    auth_methods = [
      { path = "nomad", type = "jwt", algs = ["RS256"] },
    ]

    auth_roles = concat(
      [
        for name, definition in var.agent_definitions : {
          role       = name
          audiences  = ["vault.io"]
          user_claim = "/nomad_job_id"
          policies   = [definition.ceiling_policy]
          ttl        = 300
        }
      ],
      [
        {
          role       = "harness"
          audiences  = ["vault.io"]
          user_claim = "/nomad_job_id"
          bound      = var.harness_job_id
          policies   = ["harness-database"]
          ttl        = 300
        },
        {
          role       = "conformance"
          audiences  = ["vault.io"]
          user_claim = "/nomad_job_id"
          bound      = var.conformance_job_id
          policies   = ["harness-database"]
          ttl        = 1800
        },
      ]
    )

    policies = concat(
      [
        for name, definition in var.agent_definitions : {
          name  = definition.ceiling_policy
          paths = definition.allowed_paths
        }
      ],
      [{ name = "harness-database", paths = ["database/creds/harness"] }]
    )

    secrets_engines = concat(
      [
        { path = "database", type = "database" },
      ],
      var.enable_tls ? [{ path = "pki", type = "pki" }] : []
    )

    registry_entries = [
      for name, definition in var.agent_definitions : {
        display_name     = name
        owner            = definition.owner
        ceiling_policies = [definition.ceiling_policy]
      }
    ]

    database_roles = [
      {
        name               = "harness"
        db                 = "brieve"
        default_ttl        = 3600
        max_ttl            = 86400
        grants_parent_role = true
      }
    ]
  }
}

output "digest" {
  value       = sha256(jsonencode(local.configuration_elements))
  description = "Identical across substrates, or FR-002 is false."
}

output "elements" {
  value       = local.configuration_elements
  description = "The digest's inputs, so a mismatch is diffable rather than merely reported."
}
