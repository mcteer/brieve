# SPDX-License-Identifier: Apache-2.0
#
# Attestation. The scheduler signs a workload identity; Vault verifies it against the
# scheduler's JWKS. No shared secret, nothing to place in a jobspec.

resource "vault_jwt_auth_backend" "workload" {
  path               = "nomad"
  type               = "jwt"
  jwks_url           = var.nomad_jwks_url
  jwt_supported_algs = ["RS256"]
  description        = "Workload identity (ADR-0048)"
}

# HOW MUCH CLOCK DISAGREEMENT AN ATTESTED IDENTITY SURVIVES.
#
# The scheduler signs a workload identity with ITS clock and Vault validates it with its own.
# In the dev enclave those are different machines — the Nomad agents run on the host, Vault
# runs in the container VM — so the two drift, and with no tolerance a token can be rejected
# for `nbf` before it is a second old.
#
# **Found by 020's dispatched rows**, which failed intermittently with
# `invalid not before (nbf) claim: token not yet valid` — a *different* subset of rows each
# run, each with an empty audit trail, which reads as a flaky new feature rather than an
# environment fault. The measured drift was 919 seconds on a long-running VM.
#
# 120 seconds, and it buys nothing an attacker wants. `exp` still bounds the token (the
# identity's TTL is an hour), the audience and job-id claims are still exact, and the
# signature is still the scheduler's. What it removes is a failure mode where attestation
# succeeds or fails on which of two clocks is a second ahead — which is not a security
# property, it is a lottery, and a lottery in the identity path is how people learn to
# re-run a red gate instead of reading it.
#
# It does NOT excuse real drift: the enclave's clocks should be in sync, and a drift large
# enough to exceed this is a machine to fix rather than a number to raise.
locals {
  jwt_clock_leeway = 120
}

# Per-definition agent roles. An agent's ceiling bounds what a model-chosen tool call
# may reach — and deliberately does NOT include the state store: see policies.tf.
resource "vault_jwt_auth_backend_role" "agent" {
  for_each = var.agent_definitions

  backend                 = vault_jwt_auth_backend.workload.path
  role_name               = each.key
  role_type               = "jwt"
  bound_audiences         = ["vault.io"]
  not_before_leeway       = local.jwt_clock_leeway
  clock_skew_leeway       = local.jwt_clock_leeway
  user_claim              = "/nomad_job_id"
  user_claim_json_pointer = true

  claim_mappings = {
    nomad_namespace = "nomad_namespace"
    nomad_job_id    = "nomad_job_id"
    nomad_task      = "nomad_task"
  }

  token_policies = [each.value.ceiling_policy]
  # Short by construction. A run outliving this re-authenticates; it never replays,
  # because on resume the allocation is new and so is its identity (ADR-0026).
  token_ttl  = 300
  token_type = "service"
}

# The platform's own identity, distinct from any agent's. The harness process may reach
# its state store; the agent running inside it may not.
resource "vault_jwt_auth_backend_role" "harness" {
  backend                 = vault_jwt_auth_backend.workload.path
  role_name               = "harness"
  role_type               = "jwt"
  bound_audiences         = ["vault.io"]
  not_before_leeway       = local.jwt_clock_leeway
  clock_skew_leeway       = local.jwt_clock_leeway
  user_claim              = "/nomad_job_id"
  user_claim_json_pointer = true

  # Without the bound claim, ANY workload could assume this role and the attestation
  # would be decorative — it would prove something was scheduled, not what.
  bound_claims = {
    nomad_job_id = var.harness_job_id
  }

  # Both jurisdictions: the state store to write its own record, and the harness-domain
  # ceiling to know what it may call. Read-only on the second — a run that could write its
  # own ceiling would be the escalation Principle IV exists to make structurally
  # unavailable.
  # 054 REMOVED `scratch_policy_check` FROM THIS LIST, and this note is what it left behind.
  #
  # 042 granted it, and its own comment called it "the first WRITE capability a dispatched run
  # has ever carried". Every grant below is read-only again. The measurement that needed it
  # runs on the surface now, which already held the namespace for the sweep — so a run asks for
  # a measurement rather than performing one, and holds no policy-write authority at all.
  #
  # This is 054's FR-012 met in full rather than in part. Bounding the grant per run was
  # possible and cost one permanent identity entity per Build; removing it costs nothing.
  #
  # Written ABOVE the list rather than inside it: a row asserting what this role grants reads
  # the brackets, and a comment naming the policy inside them reads as the grant itself.
  token_policies = [
    vault_policy.harness_database.name,
    vault_policy.harness_authority_read.name,
  ]
  token_ttl  = 300
  token_type = "service"
}

# The conformance suite runs as its own workload with its own identity. That is what
# lets the durability rows exercise the attestation path rather than sit beside it.
resource "vault_jwt_auth_backend_role" "conformance" {
  backend                 = vault_jwt_auth_backend.workload.path
  role_name               = "conformance"
  role_type               = "jwt"
  bound_audiences         = ["vault.io"]
  not_before_leeway       = local.jwt_clock_leeway
  clock_skew_leeway       = local.jwt_clock_leeway
  user_claim              = "/nomad_job_id"
  user_claim_json_pointer = true

  bound_claims = {
    nomad_job_id = var.conformance_job_id
  }

  # Both, because the conformance rows exercise the write path and the read path: the
  # evidence rows have to draw a real SELECT-only credential to prove Postgres refuses a
  # write through it. Proving that against a fake connection would prove nothing.
  token_policies = [
    vault_policy.harness_database.name,
    vault_policy.evidence_database.name,
    vault_policy.harness_authority_read.name,
  ]
  token_ttl  = 1800
  token_type = "service"
}

# Dispatched agent runs.
#
# Separate from the conformance role because they are separate things that happen to want
# the same database access today: one is a merge gate, the other is the product. Merging
# them would mean widening the gate's authority to widen a run's, or the reverse, which is
# exactly the coupling per-task authority exists to avoid.
#
# `bound_claims_type = "glob"` so both the parent id and any derived dispatch id are
# admissible. The identity presents the PARENT id, which is not what `nomad job status`
# shows — binding only the derived form fails every login with "claim nomad_job_id does not
# match any associated bound claim values" while the role looks correctly configured.
resource "vault_jwt_auth_backend_role" "agent_run" {
  backend           = vault_jwt_auth_backend.workload.path
  role_name         = "agent-run"
  role_type         = "jwt"
  bound_audiences   = ["vault.io"]
  not_before_leeway = local.jwt_clock_leeway
  clock_skew_leeway = local.jwt_clock_leeway

  # 054, REVERTED AFTER MEASUREMENT. This pointed at `/nomad_allocation_id` for one day.
  #
  # It worked: a run could reach only its own measurement workspace, demonstrated live. It
  # also created one Vault identity entity per Build, permanently, against a documented hard
  # ceiling of ~480,000 on integrated storage — reached in about 2.4 months at 10,000 users,
  # after which entity writes fail and entity writes happen on every login. Proposed ADR-0072
  # records the rule: identity is per definition, never per invocation.
  #
  # The isolation was kept and made stronger by moving the measurement off the run entirely
  # (054 T046c/T046d), so this can go back to naming the job — where every run shares one
  # identity that already exists and nothing accumulates.
  user_claim              = "/nomad_job_id"
  user_claim_json_pointer = true

  bound_claims_type = "glob"
  bound_claims = {
    nomad_job_id = join(",", var.agent_run_job_id_patterns)
  }

  # The harness-domain jurisdiction too, as of 010: a dispatched run resolves its own
  # ceiling, user scope, and policy from the trust fabric. Read-only — a run that could
  # write its own ceiling would be the escalation Principle IV makes structurally
  # unavailable, and it would be one line away.
  token_policies = [
    vault_policy.harness_database.name,
    vault_policy.harness_authority_read.name,
    # 013: the agent secret space pack tools read. Role-level by declared limitation —
    # see the policy's own comment; per-definition narrowing is ADR-0044's translation.
    vault_policy.agent_pack_secrets.name,
    # 027: the vendor credential a run needs when its definition binds a NON-fixture model.
    # Granted to the role rather than fetched by the surface and passed down, because the
    # allocation must read it under its own attested identity — a key handed to an allocation
    # is a key in the allocation's environment, which is what ADR-0058 exists to avoid.
    vault_policy.model_credential_read.name,
  ]
  token_ttl  = 3600
  token_type = "service"
}

# The persistent MCP service.
#
# Separate from `harness` and `agent-run` because it is a separate thing that happens to
# want the same database access: it reads dependency health, writes what its checker
# observed, and verifies evidence-stream integrity. Merging the roles would mean widening
# one workload's authority to widen another's, which is the coupling per-task authority
# exists to avoid.
#
# It carries `harness_database` and NOT `evidence_database`: integrity verification runs
# under the run role, because `audit_stream_heads` deliberately carries no grant for the
# evidence role — a read path able to see the heads could learn what it would need to
# forge.
# The northbound API. Its own role, because its job id is its own.
#
# **This did not exist, and the surface could not start without it.** `service.py` builds
# its collaborators with the default `harness` role, whose bound claim is
# `nomad_job_id = "harness"` — a job that is not the API. Every login was refused with
#
#     claim "nomad_job_id" does not match any associated bound claim values
#
# which names the claim rather than the missing role, and the allocation died in
# `audit_sink.migrate()` before serving a request. Nothing downstream of `build()` had
# ever run in a deployed enclave, which is the shape of every "correct, tested, wired to
# nothing" finding this feature turned up: the assembly was never exercised because the
# process it assembles never started.
#
# Three policies, matching what the assembly actually constructs. Listed rather than
# borrowed from `harness`, so that widening one workload's authority is not a side effect
# of widening another's.
resource "vault_jwt_auth_backend_role" "api" {
  backend                 = vault_jwt_auth_backend.workload.path
  role_name               = "api"
  role_type               = "jwt"
  bound_audiences         = ["vault.io"]
  not_before_leeway       = local.jwt_clock_leeway
  clock_skew_leeway       = local.jwt_clock_leeway
  user_claim              = "/nomad_job_id"
  user_claim_json_pointer = true

  bound_claims = {
    nomad_job_id = var.api_job_id
  }

  token_policies = concat([
    # The run index, thread store, audit sink, durability provider and change-request
    # store — every one of which the assembly migrates at start.
    vault_policy.harness_database.name,
    # The evidence read path draws its own SELECT-only credential, deliberately separate:
    # the surface that serves evidence must not be able to write it.
    vault_policy.evidence_database.name,
    # Ceilings, role bindings, the model matrix — and the claim-to-role mappings, without
    # which `resolve_roles` returns empty and this surface refuses everyone.
    vault_policy.harness_authority_read.name,
    # 027: the vendor credential `ask` brokers per question. Granted here as well as to the
    # served MCP surface, because ADR-0033 is a statement about what a DEPLOYMENT does — a
    # posture wired into one assembly and not the other would make surface parity a claim
    # about a test fixture.
    vault_policy.model_credential_read.name,
    # 044: THE FIRST WRITE CAPABILITY THIS SURFACE HAS EVER HELD against the trust fabric.
    #
    # Every grant above is read-only, and that was true of every role in this module until
    # 042 gave a dispatched run its scratch namespace. This one is bounded the same way —
    # by the RECORDS it names, not by withholding the verb — and what it enables is a person
    # originating a governance change without holding estate credentials.
    #
    # The gated variant is attached alongside when a quorum is configured; with none, this
    # grant applies changes directly and the console is required to disclose that.
    vault_policy.authority_submit.name,
    ],
  local.control_groups_enabled ? [vault_policy.authority_submit_gated[0].name] : [])
  # Long-lived by design, like the mcp service, and still a TTL rather than none — the
  # difference between a re-issued identity and a standing credential.
  token_ttl  = 3600
  token_type = "service"
}

# 019's served surface. Its own role, because it is its own job.
#
# **The API paid for getting this wrong once**: it asked for a role bound to a different
# `nomad_job_id`, so it never started at all — and the failure named authentication rather
# than the binding. A served surface with no matching role is a service that comes up,
# presents an attestation nothing accepts, and reports a Vault problem.
#
# Policies are the API's exactly, and deliberately so: this surface serves the SAME
# operations against the SAME core as the calling user. A different policy set would make
# ADR-0033's parity guarantee a claim about two differently-privileged services.
resource "vault_jwt_auth_backend_role" "mcp_surface" {
  backend                 = vault_jwt_auth_backend.workload.path
  role_name               = "mcp-surface"
  role_type               = "jwt"
  bound_audiences         = ["vault.io"]
  not_before_leeway       = local.jwt_clock_leeway
  clock_skew_leeway       = local.jwt_clock_leeway
  user_claim              = "/nomad_job_id"
  user_claim_json_pointer = true

  bound_claims = {
    nomad_job_id = var.mcp_surface_job_id
  }

  token_policies = [
    vault_policy.harness_database.name,
    vault_policy.evidence_database.name,
    vault_policy.harness_authority_read.name,
    # 027: the vendor credential `ask` brokers per question. This surface is the one with a
    # person on the other end of it, so it is the first place the platform ever calls a model
    # on somebody's behalf.
    vault_policy.model_credential_read.name,
    # 042: the scratch sweep. This service already hosts the resume sweeper and the
    # dependency checks because both needed a long-lived home, and an orphaned measurement
    # policy is the same shape of problem — something a dead run left behind that only a
    # living process can clear.
    #
    # The SWEEP grant, not the run's: `list` over the policy namespace, which a dispatched
    # run does not get. "Always destroyed" is a claim; this is what lets a machine check it.
    vault_policy.scratch_sweep.name,
  ]
  token_ttl  = 3600
  token_type = "service"
}

resource "vault_jwt_auth_backend_role" "mcp" {
  backend                 = vault_jwt_auth_backend.workload.path
  role_name               = "mcp"
  role_type               = "jwt"
  bound_audiences         = ["vault.io"]
  not_before_leeway       = local.jwt_clock_leeway
  clock_skew_leeway       = local.jwt_clock_leeway
  user_claim              = "/nomad_job_id"
  user_claim_json_pointer = true

  bound_claims = {
    nomad_job_id = var.mcp_job_id
  }

  token_policies = [
    vault_policy.harness_database.name,
    vault_policy.harness_authority_read.name,
    # 015: the mcp service is the only workload that ships to the second copy, because it
    # is the only one running the supervisory loop. One path, read-only — and not the
    # jobspec's env block, where the credential's SELECT half would be readable by anyone
    # with scheduler access.
    vault_policy.audit_egress_credential.name,
  ]
  # Longer than a batch job's, because this one is long-lived by design — and still a TTL
  # rather than none, which is the difference between a re-issued identity and a standing
  # credential.
  token_ttl  = 3600
  token_type = "service"
}
