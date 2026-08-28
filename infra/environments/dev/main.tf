# SPDX-License-Identifier: Apache-2.0
#
# Development root: substrate-docker + trust-fabric.
#
# Compare this file with ../production/main.tf. The ONLY differences are which substrate
# module is composed and which profile is selected. That the delta is visible in the file
# layout — rather than hidden in a conditional inside a shared file — is what makes
# FR-002 checkable by reading rather than by tracing.

terraform {
  required_version = ">= 1.9"
  required_providers {
    docker = { source = "kreuzwerker/docker", version = "~> 3.0" }
    vault  = { source = "hashicorp/vault", version = "~> 4.4" }
  }
}

provider "docker" {}

provider "vault" {
  address = module.substrate.vault_address
  token   = var.vault_token

  # Explicit rather than ambient. Once the listener is on TLS the provider must trust the
  # control plane's CA, and leaving that to VAULT_CACERT in the caller's environment
  # means an apply that works for whoever set it and fails for everyone else — with
  # "failed to lookup token", which names neither TLS nor the CA.
  ca_cert_file = var.ca_cert_file
}

module "substrate" {
  source             = "../../modules/substrate-docker"
  vault_host_network = var.vault_host_network
  vault_license      = var.vault_license

  tls_certificate = var.tls_certificate
  tls_private_key = var.tls_private_key
}

locals {
  # Override only authoring-agent's write pin. Every other definition is passed through
  # unchanged so a laptop auto.tfvars cannot silently rebind planner/applier/ask.
  agent_definitions = {
    for name, definition in var.agent_definitions :
    name => merge(definition, name == "authoring-agent" ? {
      binding_map = merge(definition.binding_map, { write = var.authoring_write_cell })
    } : {})
  }
}

module "trust_fabric" {
  source = "../../modules/trust-fabric"

  nomad_jwks_url     = module.substrate.nomad_jwks_url
  database_endpoint  = module.substrate.database_endpoint
  collector_endpoint = module.substrate.collector_endpoint
  profile            = "development"
  enable_tls         = var.enable_tls

  agent_definitions   = local.agent_definitions
  role_bindings       = var.role_bindings
  definition_policies = var.definition_policies
  model_matrix_cells  = concat(var.model_matrix_cells, var.extra_model_matrix_cells)
  ask_binding         = var.ask_binding

  # 027. Dev seeds a clearly-marked non-functional credential so `make dev-up`'s ask
  # progression reaches a fetch that SUCCEEDS and a vendor call that fails — one link past
  # `credential_unavailable`, proving the mount, the policy, the attested read and the provider
  # construction without a real key existing anywhere in dev. Production leaves this false and
  # writes the record out of band, so an apply can never overwrite a real credential with a dud.
  seed_model_credential_placeholder = true
  seed_dev_claim_mapping            = true

  # 054, T011a. Admits the run-shaped identity probe (`infra/jobs/run-probe.nomad.hcl`) to the
  # `agent-run` role, so a conformance row can attempt a real break-in under real run
  # authority. Three cheaper routes are closed — see 054 research R7 — and a row that minted
  # its own authority would go green while asserting nothing.
  #
  # **SET HERE AND NOT IN THE MODULE**, deliberately. The module default stays
  # `["agent-run", "agent-run/dispatch-*"]`, listed explicitly rather than globbed because
  # `agent-run*` would also admit a job named `agent-runner`. Production inherits that default
  # and never admits the probe: a test-only job id is admissible only where the enclave is
  # itself a test enclave.
  agent_run_job_id_patterns = ["agent-run", "agent-run/dispatch-*", "harness-run-probe"]
}
