# SPDX-License-Identifier: Apache-2.0
variable "agent_definitions" {
  type = map(object({
    description    = string
    owner          = string
    ceiling_policy = string
    allowed_paths  = list(string)
  }))
}

variable "harness_job_id" {
  type    = string
  default = "harness"
}

variable "conformance_job_id" {
  type    = string
  default = "conformance"
}

variable "enable_tls" {
  type    = bool
  default = false
}
