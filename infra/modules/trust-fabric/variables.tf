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
    # The HARNESS-DOMAIN ceiling — a different jurisdiction from the two fields above
    # (ADR-0044). Those bound which secrets a run's token may read; these bound which
    # tools an agent may call. Neither is derivable from the other, which is why both
    # are authored rather than one being generated from the other.
    tool_names      = list(string)
    product_actions = list(string)
    # 013. `optional` with defaults rather than required fields, because every definition
    # authored before packs existed must keep applying unchanged — 008-012's fixtures name
    # no pack and are what a dozen conformance lanes run against.
    #
    # The defaults are the narrowest thing that still runs: no packs reached, no model
    # bound, and tier 1, which is paved paths only. A definition that acquired capability
    # by omission would be the widening FR-005 forbids, arriving through a variable default.
    packs       = optional(list(string), [])
    binding_map = optional(map(string), {})
    tier        = optional(number, 1)
  }))
}

variable "ask_binding" {
  description = "Which qualified cell an ask may use, per source (026). Absent means every ask refuses `unbound`."
  type = object({
    # Cell references (`pack:model:role`) whose role MUST be `ask`. Either may be empty: a
    # source with no cell named refuses for that source alone, which is an operator saying
    # "not yet" legibly rather than a malformed record.
    guidance_cell = optional(string, "")
    estate_cell   = optional(string, "")
  })
  default = {}
}

variable "model_matrix_cells" {
  description = "Qualified Model Matrix cells (pack × model × role), the only models a binding map may name (ADR-0022/0039, Principle VIII)."
  type = list(object({
    pack = string
    # `provider/model@version`. `MODEL_IDENTIFIER` refuses an alias or a bare name at parse,
    # because "latest" resolving differently next week is auto-tracking under another name.
    model = string
    # One of ask / plan / write / judge / summarize — ADR-0039's closed vocabulary. A cell
    # qualified to summarize does not qualify a model to write.
    role = string
    # `fixture` (qualified against a recording) or `live` (a real model answered). Carried
    # per cell because the difference is invisible otherwise, and it matters most for
    # `write` — a model permitted to make changes.
    qualified_by = string
    # Which judge scored it. Empty only for the seed-qualified first judge.
    judge = optional(string, "")
    # A cell qualified once and since pulled. Withdrawal is the case run-start validation
    # exists for: the definition pinning it sits unchanged in the registry, so validating
    # only at registration would let a withdrawn cell keep running because nothing re-asked.
    withdrawn = optional(bool, false)
  }))
  # EMPTY BY DEFAULT, and deliberately not "a sensible starter cell". An empty matrix
  # refuses every binding map, which is the correct posture for an estate that has not run
  # its eval gates: a default cell would qualify a model by omission, which is exactly the
  # ungated promotion Principle VIII forbids. Environments author their own.
  default = []
}

variable "role_bindings" {
  description = <<-DESC
    What a claim-derived role means in the harness domain.

    The same jurisdiction as an agent's ceiling — both answer "what may this principal
    call" — so the same store, the same governance, and the same reader. A person's role
    and an agent's definition meet as peers in Principle IV's intersection, and giving
    them different homes would suggest they are different kinds of thing.
  DESC
  type = map(object({
    tool_names      = list(string)
    product_actions = list(string)
  }))
  default = {}
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

variable "api_job_id" {
  description = "Scheduler job id serving the northbound API."
  type        = string
  default     = "api"
}

variable "conformance_job_id" {
  description = "Scheduler job id running the conformance suite under its own identity."
  type        = string
  default     = "conformance"
}

variable "mcp_job_id" {
  description = <<-DESC
    Scheduler job id of the persistent MCP service.

    A plain id rather than a glob: the service is a `service` job with one name, unlike
    dispatched runs whose ids derive from a parameterized parent.
  DESC
  type        = string
  default     = "mcp"
}

variable "mcp_surface_job_id" {
  description = <<-DESC
    Scheduler job id of the SERVED MCP surface — 019.

    Distinct from `mcp_job_id`, which is the supervisory loop. FR-015a requires the two be
    independently available, so they are two jobs, two identities, and two roles. A single
    role covering both would make a protocol crash and a sweeper crash the same event to
    everything downstream.
  DESC
  type        = string
  default     = "mcp-surface"
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

variable "definition_policies" {
  description = <<-DESC
    Policy narrowing a definition below its ceiling, keyed by agent definition id.

    Empty is the normal state. A policy is how an operator tightens a definition without
    editing its ceiling — for an incident or a migration — and it is read on every step so
    the narrowing takes effect on the next one rather than at the next run.
  DESC
  type = map(object({
    tool_names      = list(string)
    product_actions = list(string)
  }))
  default = {}
}

variable "collector_endpoint" {
  description = <<-DESC
    host:port of the second copy (015), as reachable FROM the trust store's container —
    which is not where the operator's shell reaches it. Coordinates, not a secret.
  DESC
  type        = string
}

variable "collector_database" {
  description = "Database name at the second copy."
  type        = string
  default     = "collector"
}

variable "collector_shipper_username" {
  description = "The append-only account the collector's operator issued to the platform."
  type        = string
  default     = "harness_shipper"
}

variable "collector_shipper_bootstrap_password" {
  description = <<-DESC
    The one-time value the collector's operator hands over. Vault rotates it on import, so
    the password in force afterwards is known to nothing but Vault and this value stops
    working immediately — the same disposition `rotate-root` gives the state store's
    bootstrap credential. Not marked sensitive for that reason: treating a deliberately
    dead value as a secret would misrepresent which credentials actually matter here.
  DESC
  type        = string
  default     = "dev-only-shipper"
}
