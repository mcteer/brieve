# SPDX-License-Identifier: Apache-2.0
#
# SC-001, made runnable without infrastructure.
#
# The comparison holds PROFILE constant and varies SUBSTRATE, because those are the two
# declared axes and only one of them is claimed to be neutral. Production enabling TLS is
# a profile difference and is supposed to show up; the substrate changing nothing is the
# claim under test.

terraform {
  required_version = ">= 1.9"
}

variable "agent_definitions" {
  type = map(object({
    description    = string
    owner          = string
    ceiling_policy = string
    allowed_paths  = list(string)
  }))
  default = {
    "demo-agent" = {
      description    = "Reference registration proving the ADR-0015 registry flow"
      owner          = "platform"
      ceiling_policy = "agent-ceiling-demo"
      allowed_paths  = ["secret/data/demo/*"]
    }
  }
}

# Same inputs, same profile. The substrate each would run on is different and, by
# construction, invisible here — which is the whole point.
module "as_scheduled_on_containers" {
  source            = "../../modules/configuration-digest"
  agent_definitions = var.agent_definitions
  enable_tls        = false
}

module "as_scheduled_on_hosts" {
  source            = "../../modules/configuration-digest"
  agent_definitions = var.agent_definitions
  enable_tls        = false
}

output "digest_containers" { value = module.as_scheduled_on_containers.digest }
output "digest_hosts" { value = module.as_scheduled_on_hosts.digest }
output "identical" { value = module.as_scheduled_on_containers.digest == module.as_scheduled_on_hosts.digest }
output "elements_containers" { value = module.as_scheduled_on_containers.elements }
output "elements_hosts" { value = module.as_scheduled_on_hosts.elements }
