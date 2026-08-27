# Changelog

User-visible changes. The PR template still prompts for the entry; this file is the
durable record.

## Unreleased

### Build

- **Adopted skills now reach the phases bound to them.** A pack declares `phases` on each
  `[[skills]]` entry, and that phase's model receives the skill's bytes alongside its
  instruction, digest-verified again at delivery. The Terraform pack binds
  `terraform-style-guide` and `terraform-style-guide-security` to `plan`, `write` and
  `judge`; both were pinned and delivered to nobody before. `research` and `propose` stop
  claiming practice they do not receive, and so do all five Vault phase files. A phase bound
  to no skill is byte-identical to what it was. Missing, empty, drifted, or over-budget
  content stops the phase with its own reason code; nothing is ever truncated. Terraform and
  Vault instruction cards are **0.3.0**.
- **A pull request says what the platform could not carry out.** The vendored style guide
  recommends `terraform fmt -recursive` and `terraform validate`, and no registry tool offers
  either, so an `## Adopted practice not carried out` section names them for the reviewer.
  The text comes from the manifest, never from a model, and is identical across runs.
- **Measured, and reported as measured:** delivering these two skills did **not** change what
  Write authors on the current corpus (Sonnet 5, n=5 per arm, 2026-08-27). Validation blocks
  appeared 5/5 with the skills and 5/5 without; shared tagging appeared 0/5 either way. The
  delivery mechanism is proven byte-for-byte, and its behavioural yield on this model is
  zero — the rules these skills teach are either already in the model or already restated by
  hand in the phase cards. Re-run with `evals/prompt-tune/sc002_skill_effect.py`.
- **`content_pins` skill keys now name the binding** — `<pack>/skills/<name>@plan+write+judge`
  or `@unbound`, replacing `<pack>/<name>` with no compatibility shim. What each phase
  actually received is recorded separately as phases bind, so a run that stopped before Write
  is not readable as one whose Write model saw the skill.

- Each Build phase is steered by a pinned pack file `packs/<pack>/agents/<phase>/AGENTS.md`
  (Terraform and Vault). Ask and the portal do not compose those files. Missing or empty
  instructions fail the phase and do not open a pull request. Terraform cards are
  **0.2.0**: production-shaped after individual GEPA (no eval-lane FILE protocol, no
  grading overlay). On the live authoring lane (n=5, Sonnet 5, Terraform 1.15.8) the
  promoted Write card scored **5/5** on both ``terraform validate`` and the property
  detector against a same-n generic of 5/5 tooling and 2/5 reference (25 Aug, n=5,
  Sonnet 5, Terraform 1.15.8). Vault cards are **0.2.0** on the same production-shaped
  pattern. SC-006's Vault half is the per-phase GEPA record plus those pins — the live
  authoring subjects are Terraform repositories, not a 5/5 on ``terraform validate``. The
  authoring pin detector treats HashiCorp ``~>`` as a pin (a ceiling exists);
  ``>=`` and ``*`` remain floating.
- Write refuses dotenv templates (``.env``, ``.env.example``) instead of
  opening a pull request that only adds placeholder env files.
- Write no longer treats “named nothing” as done while planned files are still
  missing, and tells the model which paths remain instead of rewriting one
  module three times. Later files now see bounded bodies of files already
  written, so outputs and variables cannot invent a second stack. Judge deny
  reasons are no longer cut off mid-sentence.
- The signed-in operator can start Build: the role binding includes the authoring tools
  the definition's ceiling already names. Without them, manufacture refused even though
  the portal accepted the request.
- The API allocation now copies capability packs into the process tree, so Build can
  see that terraform declares an authoring workflow. Without that copy every Build was
  refused as undeclared.
- A finished Build that opened a pull request now shows the link. Publish wrote
  the URL, then the proposer restored the analyzer snapshot and wiped it, so the
  page reported "Ended without a pull request" while GitHub had the PR.
- Terraform-shaped Build runs a real `terraform plan` against the authored tree
  before Judge. A failed plan (or a missing Terraform binary) does not open a
  pull request. A successful plan’s bounded output is evidence on the PR.
  The authoring image pins Terraform 1.15.8; the analyzer fails `tooling_missing`
  at start if the binary is absent.

### Local stack

- Laptop bring-up is `bash deploy/local/stack.sh up`, with a step-by-step guide in
  `docs/development/local-stack.md`. Ask does not need a demo app; Build that opens a
  pull request still needs a GitHub repo with the Brieve App installed.
- Terraform 1.15 no longer fails seeding the development sign-in mapping (`\x00` in a
  quoted string). The key is stored as a literal that must match Python's `mapping_key`.
- After `git pull`, run `stack.sh up` again. A stack left running still has yesterday’s
  Vault role bindings; Build then dies immediately with `task scope exceeds user or
  ceiling`. On the laptop, `ASK_MODEL` also binds Build’s write cell (gitignored
  `laptop.auto.tfvars`); CI stays on the fixture. `stack.sh up` seeds the vendor key
  and GitHub App key into Vault from `.env` paths. Without `ASK_MODEL`, Research still
  fails in seconds (`could not name a permitted tool after 3 attempt(s)`).
  After `up` recreates the sign-in helper, Sign in again — a leftover session is
  unverifiable, not an outage, and the build list is not lost.

### Build

- The final Terraform plan gate is removed. It ran `terraform plan` against the authored
  tree in the dispatch container, with `-backend=false` and no state, and refused to open a
  pull request unless it came back clean. A plan is only true of the environment it ran
  against: that one was not the target estate, so a green result was never evidence about
  the target and the same configuration could plan clean there and fail on apply where it
  was going. It also refused correct work, because a configuration declaring a remote
  backend cannot be planned without initialising that backend. The check now belongs to
  whoever receives the pull request, against their own state and credentials. Judge deny,
  ownership failure and publish error still block. `terraform_plan` remains a tool the model
  may call for context; the PR no longer carries plan output as evidence.
  Spec 047 and ADR-0068 both carry dated withdrawal notes; ADR-0068's Vault decision
  is unaffected.

### Portal

- Signed-in empty home is one create stage: HashiCorp mark and
  an Ask/Build slider (Ask by default). History combines conversations and
  Builds. Stop for a running Ask or Build sits in the composer bubble.
- The conversation stage lines up: transcript and composer share one measure
  (`--stage-column`) instead of 680px beside 56rem, the item title reads from the
  left of the topbar rather than its centre, and the answer is the largest, fullest
  contrast prose in the transcript rather than the smallest and dimmest. Once an
  answer arrives in place, home becomes the open-item stage — the create mark no
  longer sits above a conversation. Column rows are one line and one left edge; the
  verb slider is sentence case.
- The Build phase table shows only the phase status. The failure write-up
  stays under the table, not in the Judge row.
- Ask and Build share one dark conversational shell (icon rail, per-verb list, thread,
  composer). The composer is 56% width, with the action at
  the bottom right. Enter sends; Shift+Enter writes a line. While Ask is in flight the
  same control becomes **Stop**. An in-flight Build has no second composer — **New** in
  the Builds list starts another run, and **Stop** sits in the header. Starting a Build
  no longer reloads the page: the run column lands in the existing shell and the address
  updates, matching Ask. Without JavaScript the form still 303s to the run page. Header
  Stop (and Ask Delete) use the same chip as New, not a native browser button. The
  Nocturne palette (violet accent, semantic stage colours) replaces the copper theme;
  UI type is Roboto, evidence stays IBM Plex Mono. In-flight Build shows the stored opening message
  when the platform already holds it (`intake_message` on `GET /runs/{run_id}/result`).
