# The model vendor credential — the platform's second named standing-credential exception.
#
# **Principle IV v1.4.0 and ADR-0058.** A model vendor authenticates with a static key and
# validates no workload identity, so ADR-0044's federate-or-broker rule routes it here: the
# credential is held once, in the trust store, and delivered per task to a workload that reads it
# under its own attested identity and never persists it.
#
# **Its own mount, not a record under `harness-authority`.** That mount is the tool-authorization
# jurisdiction — ceilings, role bindings, the matrix — and every one of those records is a
# statement about *what a principal may do*. This is material. Putting a credential among
# authority records would mean any future widening of the harness-authority read grant silently
# widened access to a vendor key, which is exactly the kind of coupling the two-jurisdiction
# split in ADR-0044 exists to prevent.
resource "vault_mount" "model_credentials" {
  path        = "model-credentials"
  type        = "kv"
  options     = { version = "2" }
  description = "Model vendor credentials, brokered per task (ADR-0058, Principle IV exception 2)"
}

# Read-only, for the two workloads that call a model.
#
# **No write capability, for the same reason the ceiling policies have none**: a workload that
# could write its own vendor credential could grant itself authority to call a model, and the
# whole posture rests on the store being the only place that authority comes from. The write path
# is the operator's, under Control Group in production posture.
#
# **The exact path AND the glob.** 020 paid for this once and 026 paid for it again: a Vault glob
# does not match the empty remainder, so `model-credentials/data/*` covers
# `model-credentials/data/anthropic/something` and NOT `model-credentials/data/anthropic`. The
# reader asks for the second. A missing grant answers 403, and the 403-not-404 trap turns that
# into "the trust fabric is unreachable" — an outage report for a policy line. Both forms are
# written here so nobody adds only one later.
resource "vault_policy" "model_credential_read" {
  name   = "model-credential-read"
  policy = <<-HCL
    path "${vault_mount.model_credentials.path}/data/*" {
      capabilities = ["read"]
    }
    # KV v2 keeps the rotation generation on the metadata path. The reader takes the version
    # from the `data/` read's own envelope, so this grant is for enumeration by an operator
    # rather than by the reader — and `list` alone reveals which vendors exist, never a value.
    path "${vault_mount.model_credentials.path}/metadata/*" {
      capabilities = ["read", "list"]
    }
  HCL
}

# The dev placeholder — deliberately non-functional, and seeded rather than absent.
#
# **What it does NOT do, measured rather than assumed.** The plan claimed this would make
# `make dev-up`'s ask progression reach a fetch that succeeds and a vendor call that fails. It
# does not, and cannot: dev's matrix holds only `fixture:` cells, and governance is checked
# before the credential. With `ASK_MODEL` set to a real model the ask refuses `unqualified_cell`
# and the store is never read (confirmed by running it, not by reading the code); with it unset
# there is no provider to build. Either way the dud is not reached by an ask.
#
# **So why seed it at all.** Two reasons that survive the correction. The enclave readability row
# reads this record directly, under the operator's identity, and proves the mount, the policy and
# the KV shape are as applied rather than as declared. And it means the deployed demonstration —
# once an operator has qualified a real cell, which is eval-gated work this feature deliberately
# does not do — starts from a path that is already wired rather than one nobody has exercised.
#
# **What the vendor answers to a dud is confirmed at run, not predicted.** A rejected key may
# surface as `provider_unavailable` or as a provider fault depending on how the API answers; the
# design depends only on the fetch succeeding and the call being attempted.
#
# The value says what it is. A plausible-looking placeholder would be worse than no placeholder:
# somebody would eventually wonder whether it was real.
resource "vault_kv_secret_v2" "model_credential_dev_placeholder" {
  count = var.seed_model_credential_placeholder ? 1 : 0

  mount = vault_mount.model_credentials.path
  name  = "anthropic"

  data_json = jsonencode({
    api_key = "PLACEHOLDER-NOT-A-CREDENTIAL-dev-only-vendor-calls-will-fail"
  })
}

variable "seed_model_credential_placeholder" {
  description = <<-DESC
    Seed a clearly-marked non-functional model credential so the record, mount and policy exist
    and are readable. Dev only — and NOT a way to exercise an ask end to end, since governance
    refuses before the credential is sought while the matrix holds only fixture cells. Production
    writes the record out of band, under Control Group, and this stays false so an apply can never
    overwrite a real credential with a dud.
  DESC
  type        = bool
  default     = false
}
