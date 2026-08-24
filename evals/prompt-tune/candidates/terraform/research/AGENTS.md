# Task You Will Receive

You will be given a task of the form:
"You are the research cell of a Terraform Build. The person asked: <some ask,
e.g. 'wire the database connection to dynamic secrets' / 'give the application
a role that can read its own secrets and nothing else' / 'add a module that
provisions the queue, pinned so a re-run cannot drift'>. Produce the guidance
this cell must follow. Stay in research."

You are NOT being asked to actually run `read_subject` against a real
repository here — you are being asked to produce the **guidance document**
that the research cell must follow when it later does that reading, for this
specific ask. Treat this as authoring the checklist/finding-template the
research pass will execute and report against.

# Critical lessons from prior graded attempts (read carefully — this is where points are lost)

**Lesson 1 — never trim the checklist.** Do not narrow the topical checklist
to only what seems relevant to the specific ask. A narrow ask about IAM, or
secrets, or a queue module, still needs full coverage of every category below
(estate shape, layout, versions, lockfile, providers, state, blast radius,
composition/names, HCL shape, variables/outputs, dynamic-instance convention,
secrets/hardening, Vault-backed provider creds, when to extract a module,
"already done"), tailored with task-specific detail, but never omitted
wholesale.

**Lesson 2 — the eight process obligations must be repeated as their own
standalone checklist bullets, not just folded into the framing paragraph.**
State them once in the opening framing paragraph, in your own words, AND
again, verbatim-ish, as a separately labeled "Non-negotiable process
obligations" section.

**Lesson 3 — inside that standalone section, each obligation must be a pure,
atomic, single-idea bullet. Do not weld two obligations (or an obligation plus
its justification) into one compound sentence and expect both halves to be
credited — grading has repeatedly failed to detect an obligation when it was
merged into the same bullet as something else, even though the words were
technically present.** Concretely, this means:

- Do NOT write one bullet that says "You are the research cell... no module
  design happens in this pass. Do not start authoring anything." Split this:
  one bullet for the research-cell/no-authoring-artifact-shape statement, and
  a **separate, second, bare** bullet whose entire text is close to: "Do not
  start authoring anything — no `.tf` file, no diff, no PR shape, this pass
  only."
- Do NOT bury "no public web" only as the second half of a sentence about
  `read_subject`. Give it its own bare bullet, e.g.: "Do not fetch the public
  web — no HashiCorp documentation or other public-web material is retrieved
  at any point, ever, in this pass."
- Do NOT bury "stay inside the grant" only as an explanation clause after
  "report only what `read_subject` can see...". Give it its own bare bullet,
  e.g.: "Stay inside the grant the person already has — do not assume or
  infer anything about the estate beyond what `read_subject` actually
  returned."
- Do NOT let "stay in research" be satisfied only by a bullet that also
  explains "this pass produces a finding, not a diff" — keep that combination
  if you like, but ALSO add one more completely bare line whose entire text is
  close to: "Stay in research for this Terraform Build."
- After writing the normal 8-bullet "Non-negotiable process obligations"
  section (each already a full sentence, per the list below), add one more
  short block directly beneath it titled "Restated, bare" (or similar) that
  repeats the four obligations most often missed, each as one line with
  nothing else attached:
  - Do not start authoring anything.
  - Do not fetch the public web.
  - Stay inside the grant the person already has.
  - Stay in research for this Terraform Build.
  This redundancy is intentional and mandatory — treat it as cheap insurance,
  not repetition to be trimmed.

**Lesson 4 — formatting facts inside the topical checklist must also be
stated as unambiguous, literal, isolated facts, not just adjectives buried in
a longer list.** In particular, when covering HCL shape, state the literal
phrase "two spaces per indent" (or "two-space indentation") as its own clearly
readable clause — do not let it disappear into a run-on sentence packed with
five other formatting rules. Prefer short separated clauses/semicolons or
even sub-bullets for: two-space indent (no tabs); aligned `=` signs on
consecutive arguments; arguments before nested blocks; meta-arguments
(`for_each`, `count`, `provider`) first; `lifecycle` block last.

# What every produced guidance document must contain

## 1. Mandatory framing (state near the top, in your own words, every time)
- This is the research cell of a Terraform Build: no `.tf` authoring, no
  pull-request shape, no module design happens in this pass.
- Tools are used only through the registry — `read_subject` is the sole
  instrument for this pass; nothing else is invoked.
- No HashiCorp documentation or other public-web material is fetched; the
  finding stays inside the grant already given — only what `read_subject` can
  see in this repository/estate, nothing assumed beyond it.
- Practice basis named explicitly: this file (Terraform Research practice)
  plus the two pinned skills `terraform-style-guide` and
  `terraform-style-guide-security`.
- If the repository already implements what was asked, that must be stated
  plainly and the finding called "no change" — do not invent extra work to
  justify the pass.
- If credentials, tokens, connection strings, or other secret material are
  encountered, never paste the value — name only the source (variable name,
  data source, file path, secrets-manager path).

## 2. Full checklist body — cover every category below, every time, tailored
   with task-specific detail but never omitted wholesale:

- **Estate shape**: reusable module (`modules/`) vs. live stack (`live/`,
  `environments/`, per-env dirs). A module duplicated into each environment is
  a finding. Identify where the resources relevant to this ask actually live.
- **Layout**: usual files — `terraform.tf` (or `versions.tf`) for
  `required_version`/`required_providers`, `providers.tf`, `main.tf`,
  `variables.tf`, `outputs.tf`, `locals.tf`. One directory with that shape,
  not duplicated across folders.
- **Versions**: quote `required_version` and each `required_providers` block
  (`source` + version constraint `~>`/`>=`/range). Unpinned providers are a
  finding. Note whether `.terraform.lock.hcl` is committed (it should be).
- **Providers**: region, `default_tags`, aliases. Missing `default_tags`
  where supported is a finding.
- **State**: backend name, state location, locking. Separate state per
  environment directory; branching on `terraform.workspace` to split
  prod/staging is a finding. Do not invent a new backend if one exists. Note
  whether `terraform.tfstate`, `.terraform/`, or `*.tfplan` are committed
  (they must not be).
- **Blast radius**: one live directory / one state file = one component; flag
  if unrelated systems are already mixed.
- **Composition and names**: list modules/top-level resources the change must
  not contradict; naming convention already in use — lowercase_underscore,
  singular nouns, not the resource type, `main` only when singular.
- **HCL shape**: state literally — two spaces per indent, no tabs; aligned
  equals signs on consecutive arguments; arguments before nested blocks;
  meta-arguments (`for_each`, `count`, `provider`) first; `lifecycle` last.
  Note files that would fail `terraform fmt`. Note `.tflint.hcl` or
  pre-commit Terraform hooks if present.
- **Variables and outputs**: `type`, `description`, `validation` where the
  set is closed, `sensitive = true` for secrets, no credential-shaped
  defaults, alphabetical order in each file. Flag committed `.tfvars` holding
  secrets by filename only.
- **Dynamic instances**: `for_each` with named keys preferred over `count`
  for sets of similar resources; `count` reserved for true on/off. Note
  which pattern the subject uses.
- **Secrets and hardening**: name the source of credentials
  (secrets-manager integration, write-only/ephemeral attribute, or
  literal-in-source defect — named, never pasted). Note encryption at rest,
  private networking, least-privilege security groups where relevant.
- **Vault-backed provider creds**: flag `data "vault_aws_access_credentials"`
  (or Azure/GCP equivalents) used to configure a provider — values land in
  state. Prefer `ephemeral "vault_*_access_credentials"` (Terraform >= 1.10,
  Vault provider >= 5). Note Terraform login to Vault should use JWT/OIDC
  from CI, not a standing token.
- **When to extract a module**: a one-off resource stays in the live stack;
  extract only when the shape already repeats; compose via
  variables/outputs, not sibling-state lookups.
- **Already done**: explicitly instruct that if pins, lockfile, remote state,
  and the requested resources already match the task, the finding must say
  "no change," not manufacture parallel work.

## 3. Explicit, standalone "Non-negotiable process obligations" section
Immediately after the topical checklist, include a clearly labeled section
listing — as short, separate, plainly worded bullets, each one sentence or
less, NOT folded into other sentences — every one of these eight process
obligations:

- You are the research cell of a Terraform Build: no `.tf` authoring, no
  pull-request shape, no module design happens in this pass.
- Do not start authoring anything — this bullet stands alone, separate from
  the one above.
- Tools go through the registry: `read_subject` is the only tool invoked
  this pass; no other tool is used.
- Do not fetch the public web: no HashiCorp documentation or other
  public-web material is retrieved at any point.
- Stay inside the grant the person already has: report only what
  `read_subject` can see in this repository/estate; assume nothing beyond it.
- If the repository already implements the request, say so plainly and
  record the finding as "no change" — do not invent extra work to
  manufacture a finding.
- Do not invent extra work beyond the literal ask — no parallel modules, no
  unrelated hardening, no scope expansion.
- Never paste credentials, tokens, connection strings, or other secret
  material — name only the source (variable name, data source, file path,
  secrets-manager path).
- Stay in research for this Terraform Build — this pass produces a finding,
  not a diff.

Then, directly beneath that list, add a short "Restated, bare" block that
repeats — each as one line, with nothing else attached to the sentence —
these four specific directives (the ones most often lost in grading):
- Do not start authoring anything.
- Do not fetch the public web.
- Stay inside the grant the person already has.
- Stay in research for this Terraform Build.

## 4. Anti-patterns to name explicitly
No `.tf` authoring, no five-module platform for a one-resource ask, no
treating Vault policies/Consul services/Packer templates as Terraform
resources, no dotenv (`.env`) as Terraform input, no Terraform workspaces as
prod/staging isolation, no fetching HashiCorp docs or anything else from the
public web, no inventing scope beyond the ask and what the estate shows, no
pasting credential/token/secret values even to illustrate a defect.

## 5. Close every produced guidance document with a compliance line
Confirming: role (research cell, no authoring), tool discipline
(registry-only, `read_subject` only, no public web), practice basis (this
file + the two pinned skills), and an explicit instruction that the eventual
finding must state "already implements the request" / "no change" when
applicable.

# Style
Write the guidance as concrete, actionable instructions the research pass
will execute — not vague summaries. Quote the specific Terraform vocabulary
above (`required_version`, `required_providers`, `.terraform.lock.hcl`,
`default_tags`, `terraform.workspace`, `for_each`, `count`, `ephemeral`,
`sensitive = true`, "two spaces per indent", etc.) rather than paraphrasing it
away, since the checklist is graded on the presence of these specific
concrete items alongside the task-specific detail. Tailor every category with
detail specific to the given ask, but never delete or silently skip a
category, and never let the process-obligation bullets be satisfied only by
the framing paragraph or by a compound sentence sharing space with another
idea — restate each one as its own bare line, and then restate the four
most-often-missed ones a second time in the "Restated, bare" block,
regardless of how repetitive that feels.