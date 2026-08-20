# Changelog

User-visible changes. The PR template still prompts for the entry; this file is the
durable record.

## Unreleased

### Build

- Each Build phase is steered by a pinned pack file `packs/<pack>/agents/<phase>/AGENTS.md`
  (Terraform and Vault). Ask and the portal do not compose those files. Missing or empty
  instructions fail the phase and do not open a pull request. Terraform and Vault cards
  now encode HashiCorp style and security practice (layout, ``for_each``, version pins,
  ephemeral Vault credentials, deny-by-default paths). On the live authoring lane
  (n=5, Sonnet 5) the Write card and generic steer both scored 1/5 on the reference
  gate — delta 0, so that eval remains open.
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

### Portal

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
  Inter and IBM Plex Mono stay (048). In-flight Build shows the stored opening message
  when the platform already holds it (`intake_message` on `GET /runs/{run_id}/result`).
