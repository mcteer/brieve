# SPDX-License-Identifier: Apache-2.0
#
# THE SUBSTRATE BOUNDARY LIVES HERE.
#
# Exactly three inputs are substrate-derived: where workload identities are verified,
# where the state store listens, and (via the provider, configured by the root) where
# this module writes. A FOURTH substrate-derived input is the signal that the boundary
# has moved. That may be correct — but it is a deliberate change to
# specs/006-deployment-module-tree/contracts/module-interface.md, not a variable someone
# adds while solving something else.

variable "agent_definitions" {
  description = "Agent definitions registered in the agent registry, each with its ceiling policy (Principle IV)."
  type = map(object({
    description    = string
    owner          = string
    ceiling_policy = string
    allowed_paths  = list(string)
  }))
}

variable "nomad_jwks_url" {
  description = "SUBSTRATE-DERIVED. Where Vault fetches the scheduler's JWKS to verify workload identities."
  type        = string
}

variable "database_endpoint" {
  description = "SUBSTRATE-DERIVED. host:port of the state store, as reachable FROM Vault — not from the operator's shell."
  type        = string
}

variable "database_name" {
  type    = string
  default = "brieve"
}

variable "database_bootstrap_user" {
  description = "Account the database engine connects as to create dynamic roles. Never used by a workload."
  type        = string
  default     = "brieve"
}

variable "database_bootstrap_password" {
  description = "Bootstrap only; rotated out of this value on first apply. See database.tf."
  type        = string
  sensitive   = true
  default     = "dev-only-not-a-secret"
}

variable "profile" {
  description = <<-DESC
    Posture, NOT placement. A workstation could run the production profile; that it
    usually does not is convenience, not constraint. Keeping posture out of the
    substrate layer is what lets the substrate remain the only permitted delta.
  DESC
  type        = string
  default     = "development"

  validation {
    condition     = contains(["development", "production"], var.profile)
    error_message = "profile must be development or production."
  }
}

variable "seal_config" {
  description = <<-DESC
    Auto-unseal configuration, passed through untouched. Null means the environment's
    default seal (1-of-1 shamir in development). The SEAM is in scope; shipping a
    KMS-specific variant is not — implementing one would privilege a cloud and still
    leave every other operator writing their own.
  DESC
  type        = map(string)
  default     = null
}

variable "harness_job_id" {
  description = "Scheduler job id permitted to read dynamic database credentials."
  type        = string
  default     = "harness"
}

variable "conformance_job_id" {
  description = "Scheduler job id running the conformance suite under its own identity."
  type        = string
  default     = "conformance"
}

variable "agent_run_job_id_patterns" {
  description = <<-DESC
    Scheduler job ids a dispatched agent run may present.

    **Both forms, because the workload identity carries the PARENT job id** — not the
    dispatch-derived `agent-run/dispatch-<timestamp>-<hash>` that appears in `nomad job
    status`. Binding only the derived form fails every login with "claim nomad_job_id does
    not match any associated bound claim values", and the role looks correctly configured
    the whole time. The derived form is kept in case a Nomad version populates it instead.

    Listed explicitly rather than globbed to `agent-run*`, which would also admit a job
    named `agent-runner`.
  DESC
  type        = list(string)
  default     = ["agent-run", "agent-run/dispatch-*"]
}

variable "enable_tls" {
  description = "Issue control-plane certificates from the PKI engine. Production always; development opt-in."
  type        = bool
  default     = false
}

variable "quorum_policy" {
  description = <<-DESC
    Quorum on authority changes (ADR-0016). NULL means no gate — which is the development
    default and must never be the production one.

    **No default for the values themselves.** A quorum shipped by us would be a security
    posture chosen for every customer by whoever wrote this module. The customer's
    control-plane Vault administrator specifies it: humans build the foundations that
    determine how agents may behave, and the platform enforces what they set rather than
    deciding it for them.

    The bootstrap, named: this policy gates its own changes, so it cannot create itself.
    Provisioning applies it before the bootstrap credential is revoked — the same shape as
    TLS, where something outside the loop goes first. Without that sequence the control
    either never exists or keeps a permanent back door.
  DESC

  type = object({
    required_approvals   = number
    authorized_approvers = list(string)
    request_ttl          = string
  })
  default = null

  validation {
    condition     = var.quorum_policy == null || var.quorum_policy.required_approvals >= 2
    error_message = "required_approvals must be at least 2: a quorum of one is not a quorum, and FR-008 already excludes the requester's own endorsement."
  }
}
