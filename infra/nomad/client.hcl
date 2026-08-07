# SPDX-License-Identifier: Apache-2.0
#
# Scheduler agent configuration for the enclave.

# The HTTP API must listen on a routable interface: the trust store runs in a container
# and fetches the scheduler's JWKS at host.docker.internal:4646. Loopback-only would
# break attestation setup.
bind_addr = "0.0.0.0"

# ...but INTERNAL RPC must advertise loopback.
#
# With bind_addr = 0.0.0.0 and no advertise block, the agent advertises the host's LAN
# address for RPC, and its own client then dials that address to heartbeat. When the
# machine changes networks the address goes stale, the client cannot reach its own
# server, and the node goes `down` while the process keeps running and the HTTP API
# keeps answering.
#
# What that looks like from outside is worse than a crash: `nomad job run` succeeds, the
# job reports `running`, and no allocation is ever placed — so anything waiting on the
# workload waits forever. Nothing in that chain names the network.
advertise {
  http = "127.0.0.1:4646"
  rpc  = "127.0.0.1:4647"
  serf = "127.0.0.1:4648"
}

# THE CPU BUDGET, STATED BECAUSE NOMAD CANNOT FINGERPRINT IT HERE.
#
# Measured on an Apple M5 Pro: `cpu.frequency = 4`, `cpu.numcores = 18`,
# `cpu.totalcompute = 24`. Nomad read the clock as **4 MHz** rather than 4 GHz and multiplied
# it by the 6 performance cores, so the node advertised a 24 MHz budget for an 18-core
# machine. Six ordinary allocations consumed 24 of 24, and the seventh — the durability
# conformance job — was unplaceable with "Dimension cpu exhausted".
#
# What that looks like from outside is a resource problem, and it is an arithmetic one. The
# merge-blocking durability rows simply never ran locally, which is the same shape as a row
# that skips itself: the lane reports nothing rather than reporting red.
#
# 41400 = 18 cores x 2300 MHz, and 2300 is deliberately borrowed from the GitHub runner this
# repository already sizes against (`infra/jobs/conformance.nomad.hcl` records it as 4 cores /
# 9200 MHz). Conservative on purpose: the efficiency cores are slower than the performance
# ones, and a budget that overstates the machine schedules work it cannot run. This is a
# scheduling unit, not a benchmark — what it has to be is proportionate and stable.
client {
  cpu_total_compute = 41400
}

# No Consul here. Left on, the agent retries discovery every few seconds and fills the
# log with connection-refused errors that look like the real fault when something else
# breaks.
consul {
  server_auto_join = false
  client_auto_join = false
}

# The container driver refuses volume mounts unless the AGENT enables them. A stateful
# task then fails with `volumes are not enabled` and a message pointing at the jobspec,
# which is correct. Any deployment scheduling a stateful workload inherits this.
plugin "docker" {
  config {
    volumes {
      enabled = true
    }
  }
}
