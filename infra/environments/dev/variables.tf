# SPDX-License-Identifier: Apache-2.0
variable "vault_license" {
  type      = string
  sensitive = true
}

variable "vault_token" {
  description = "Bootstrap token for configuring the trust store. Retained in development deliberately — revoking it here breaks the re-apply loop, and an enclave nobody re-applies costs more safety than the token does on a workstation."
  type        = string
  sensitive   = true
}

variable "enable_tls" {
  description = "On by default. Development should exercise the same transport production uses; an opt-in security property is one most environments never opt into."
  type        = bool
  default     = true
}

variable "agent_definitions" {
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
    # 013. Declared here as well as in the module: Terraform's object-type conversion
    # silently DROPS attributes the type does not name, and the first apply of vault-agent
    # wrote packs = [] for exactly that reason — the values were in the tfvars map and the
    # root variable's type threw them away without a warning.
    packs       = optional(list(string), [])
    binding_map = optional(map(string), {})
    tier        = optional(number, 1)
  }))
  default = {
    # The 006 registration proof. Its ceiling grants a path under a mount that DOES exist
    # as of 010 — before that it named `secret/data/demo/*` with no `secret/` mounted, so
    # every assertion against it passed whether enforcement worked or not.
    "demo-agent" = {
      description     = "Reference registration proving the ADR-0015 registry flow"
      owner           = "platform"
      ceiling_policy  = "agent-ceiling-demo"
      allowed_paths   = ["secret/data/demo/*"]
      tool_names      = ["echo"]
      product_actions = []
    }

    # THE FIXTURE THAT CAN FAIL. Two definitions with deliberately different ceilings,
    # because "the ceiling bounds authority" is only demonstrable against a ceiling that
    # excludes something a run would otherwise get. One definition cannot show that: every
    # assertion would hold under a fabric that ignored ceilings entirely.
    "planner-agent" = {
      description     = "Plans but never applies — the narrow half of the ceiling pair"
      owner           = "platform"
      ceiling_policy  = "agent-ceiling-planner"
      allowed_paths   = ["secret/data/planner/*"]
      tool_names      = ["echo", "plan"]
      product_actions = ["product.workspace.read"]
      # 020. THE FIXTURE A CHOICE CAN BE REFUSED IN. Its ceiling holds `echo` and `plan` and
      # not `apply`, while `apply` is a registered tool — so a recording that names `apply`
      # produces a real over-reach refused by the existing enforcement, not a malformed
      # answer. A definition permitting everything could not show a refusal at all.
      binding_map = { plan = "fixture:fixture/scripted@1:plan" }
    }
    "applier-agent" = {
      description     = "Plans and applies — the wide half"
      owner           = "platform"
      ceiling_policy  = "agent-ceiling-applier"
      allowed_paths   = ["secret/data/applier/*"]
      tool_names      = ["echo", "plan", "apply"]
      product_actions = ["product.workspace.read", "product.workspace.write"]
      # 020. Bound to the OTHER cell, which is what makes SC-004 assertable: two definitions
      # naming different models must produce runs evidenced as having used different models.
      # With one cell in the estate that assertion would pass against an implementation that
      # never read a binding map.
      binding_map = { plan = "fixture:fixture/scripted@2:plan" }
    }

    # 013: the definition whose pack tools reach a product that actually answers. A NEW
    # record rather than a widened existing one, because the ceiling pair above is a
    # fixture whose exact bounds other rows assert — widening planner or applier would
    # move what their refusal rows refuse.
    #
    # `allowed_paths` covers the conformance probe path the vault_read handler reads;
    # `tool_names`/`product_actions` are the harness-domain ceiling naming the pack's
    # tools. `packs`, `binding_map`, `tier` land in the definition-bindings record the
    # same apply writes (optional() with narrow defaults for every other definition).
    "vault-agent" = {
      description    = "Operates Vault through the vault capability pack (013)"
      owner          = "platform"
      ceiling_policy = "agent-ceiling-vault"
      allowed_paths  = ["secret/data/conformance/*"]
      # `vault_write` joins the ceiling for 014's live re-observation rows, and it is the only
      # definition that names it. Required rather than convenient: FR-006a wants an
      # interrupted write resolved by OBSERVATION against the real product in both
      # directions, and a run whose ceiling omits the tool cannot leave an interrupted write
      # to observe — the invoke refuses before an intent is ever opened.
      #
      # It buys no Vault capability. The tool is non-repeatable with a real observer, which is
      # what makes the bracket and the re-observation real; the handler itself is a stub that
      # writes nothing (see `agent-pack-secrets`, which deliberately grants no write).
      tool_names = ["vault_read", "vault_write"]
      # Empty, with the manifest's reasoning: the pack's tools are platform-identity
      # reads (product_mode none), so there is no product action to authorize until
      # credential translation (ADR-0044) federates the user into the product.
      product_actions = []
      packs           = ["vault"]
      tier            = 1
      # 020. The resume rows drive this definition, and a model-driven run needs a bound
      # model before its first step. Same cell as `planner-agent`, because what US3 asserts
      # is durability under a chooser rather than anything about which model.
      binding_map = { plan = "fixture:fixture/scripted@1:plan" }
    }
  }
}

# The Qualified Model Matrix for the dev enclave.
#
# **These are the first cells this repository has ever authored.** 013 built the matrix
# reader, the policy grant, and the run-start validation, and every definition bound nothing
# — so `_resolve_binding_map` returned before touching the matrix on every run for seven
# features. The vocabulary was correct and load-bearing for nothing, which is 020's own thesis
# one level up from the tool choice.
#
# BOTH CELLS NAME THE `fixture` PROVIDER, and that is the merge lane's whole posture (FR-011).
# A gate that cannot run without a vendor is a gate that stops running, so the models a
# dispatched conformance run reaches replay a recording rather than calling out.
# `qualified_by = "fixture"` is the matrix's own word for exactly that, and it existed before
# this feature needed it.
#
# TWO of them, because one cannot fail. SC-004 asks that two definitions bound to different
# models produce runs evidenced as using different models, and a single cell would make that
# assertion pass against an implementation that ignored the binding map entirely.
#
# **This is not eval-gated promotion, and it must not be mistaken for it.** A `fixture` cell
# says a model was qualified against a recording; qualifying a *live* model for `write` is
# Principle VIII's gate and is human work that happens elsewhere. 020 consumes the matrix; it
# promotes nothing.
variable "model_matrix_cells" {
  type = list(object({
    pack         = string
    model        = string
    role         = string
    qualified_by = string
    judge        = optional(string, "")
    withdrawn    = optional(bool, false)
  }))
  default = [
    {
      pack         = "fixture"
      model        = "fixture/scripted@1"
      role         = "plan"
      qualified_by = "fixture"
      # The seed judge, which is the one case a cell may name none: nothing exists above it.
      judge = "seed"
    },
    {
      pack         = "fixture"
      model        = "fixture/scripted@2"
      role         = "plan"
      qualified_by = "fixture"
      judge        = "seed"
    },
    # 026's `ask` cell, seeded TOGETHER WITH the binding below that names it.
    #
    # Separately would be worse than not at all: a binding naming a cell the matrix does not
    # hold makes `make dev-up` produce a surface refusing `unqualified_cell`, which reads as
    # broken and sends whoever hits it to the matrix instead of to the missing provider.
    #
    # 027 decided the posture 026 deferred: the surfaces now broker a vendor credential per ask.
    # This fixture cell stays — it is what keeps `make dev-up` meaningful with no vendor key, and
    # what every hermetic row resolves against.
    {
      pack         = "fixture"
      model        = "fixture/scripted@1"
      role         = "ask"
      qualified_by = "fixture"
      judge        = "seed"
    },

    # THE FIRST CELLS THIS PLATFORM HAS EVER EARNED AGAINST A REAL MODEL.
    #
    # Every cell above says `qualified_by = "fixture"`: qualified against a recording, which is
    # honest about what it proves and proves nothing about a vendor. `make evals-live` had never
    # produced a clean full-lane run that anybody promoted from — 026 recorded the promotion as
    # deferred, and 027's spec deferred it again as "unrelated to posture".
    #
    # **Earned 2026-08-02**, `make evals-live` exit 0, 10 rows in 23m39s:
    #
    # - Four suites — `must_deny`, `must_decline`, `citation_accuracy`, `estate_state` — scored
    #   for BOTH packs against `anthropic/claude-opus@5`, every one under the `ask` role
    #   (`_subject(pack, "ask")`), at **majority of three samples per case**. The majority rule is
    #   not decoration: three single-sample runs once produced three different pass/fail sets.
    # - The answering and estate suites drove the PRODUCT path — `answer_question` and
    #   `answer_estate_question` — so what qualified is the platform answering, not the vendor
    #   talking. Every citation resolved against the pin before a claim shipped.
    # - `judge` names `anthropic/claude-opus@5` because the same run qualified it as the FIRST
    #   judge, against the human-labelled seed set at the >=90% floor (ADR-0052). The first judge
    #   chains to the seed and to no model above it, which is why naming it here is a provenance
    #   record rather than a circular one.
    #
    # **Inert until something binds them.** The ask binding below still pins the fixture cell, and
    # a surface with no `ASK_MODEL` offers no model to resolve against — so adding these changes
    # no behaviour today. That is deliberate: promoting a cell and choosing to use it are separate
    # decisions, and this is only the first.
    {
      pack         = "vault"
      model        = "anthropic/claude-opus@5"
      role         = "ask"
      qualified_by = "live"
      judge        = "anthropic/claude-opus@5"
    },
    {
      pack         = "terraform"
      model        = "anthropic/claude-opus@5"
      role         = "ask"
      qualified_by = "live"
      judge        = "anthropic/claude-opus@5"
    },
  ]
}

variable "ask_binding" {
  description = "Which qualified cell an ask may use, per source (026)."
  type = object({
    guidance_cell = optional(string, "")
    estate_cell   = optional(string, "")
  })
  # Both sources bound to the one seeded `ask` cell above. Per-source binding is what the
  # record supports; one cell serving both is what a dev enclave with one fixture model has.
  default = {
    guidance_cell = "fixture:fixture/scripted@1:ask"
    estate_cell   = "fixture:fixture/scripted@1:ask"
  }
}

# Supplied by the second phase of bring-up, not by a human.
#
# The bootstrap circularity, made concrete: the trust store cannot start with a
# certificate from a CA that is not yet serving. So it starts plaintext, its PKI engine
# is configured, it issues its own listener certificate, and the substrate is applied
# again with that certificate in hand. `enclave-up` drives that; these variables are how
# the second pass carries the material in.
variable "tls_certificate" {
  type    = string
  default = ""
}

variable "tls_private_key" {
  type      = string
  sensitive = true
  default   = ""
}

variable "ca_cert_file" {
  description = "Control-plane CA the provider must trust once the listener is on TLS. Written by bring-up to .enclave/ca.pem; empty while plaintext."
  type        = string
  default     = ""
}

variable "vault_host_network" {
  description = <<-DESC
    Run the trust store in the host network namespace (Linux Docker) rather than
    publishing a port (Docker Desktop). See the substrate module for why this is a
    substrate difference and not a change.
  DESC
  type        = bool
  default     = false
}

variable "role_bindings" {
  type = map(object({
    tool_names      = list(string)
    product_actions = list(string)
  }))
  default = {
    # The operator role: everything the reference agent can do, so an intersection with a
    # ceiling is bounded by the CEILING rather than by the person — which is the case the
    # ceiling rows need in order to be about ceilings at all.
    "operator" = {
      tool_names      = ["echo", "plan", "apply"]
      product_actions = ["product.workspace.read", "product.workspace.write"]
    }
    # Deliberately narrower, and the reason it exists: with only one role, "two users get
    # different authority" (SC-004) is untestable. A fixture that cannot fail is not a
    # fixture.
    "reader" = {
      tool_names      = ["echo", "plan"]
      product_actions = ["product.workspace.read"]
    }
    # 013: the subject role for the pack-dispatch row. Separate from `operator` because
    # that role's exact contents are what the ceiling-pair rows intersect against.
    #
    # `vault_write` joins in 014, and it has to join HERE as well as in `vault-agent`'s
    # ceiling — the two are independent bounds and manufacture intersects them, so a tool in
    # the ceiling and not the role refuses `task scope exceeds user or ceiling`. Which is the
    # intersection algebra working: the ceiling says what the DEFINITION may ever do, this
    # says what the SUBJECT may ask for, and neither is permission on its own.
    #
    # Found by a dispatched row rather than by reading, and that is the argument for the row:
    # the ceiling edit alone looked complete and every hermetic test still passed.
    "vault-operator" = {
      tool_names      = ["vault_read", "vault_write"]
      product_actions = []
    }
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
