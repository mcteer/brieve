# SPDX-License-Identifier: Apache-2.0
#
# Nomad client configuration for the dev enclave.
#
# The docker driver refuses volume mounts unless told otherwise — a task asking
# for one fails with `volumes are not enabled` and no hint that the fix lives in
# the agent's configuration rather than the jobspec. Any Nomad deployment that
# schedules a stateful workload needs this, so it is a constraint the production
# tree inherits rather than a dev convenience.
plugin "docker" {
  config {
    volumes {
      enabled = true
    }
  }
}
