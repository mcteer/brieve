# Changelog

User-visible changes. The PR template still prompts for the entry; this file is the
durable record.

## Unreleased

### Local stack

- Laptop bring-up is `bash deploy/local/stack.sh up`, with a step-by-step guide in
  `docs/development/local-stack.md`. Ask does not need a demo app; Build that opens a
  pull request still needs a GitHub repo with the Brieve App installed.
- Terraform 1.15 no longer fails seeding the development sign-in mapping (`\x00` in a
  quoted string). The key is stored as a literal that must match Python's `mapping_key`.
- Nomad keeps running after the start command returns (detached session), so the portal
  no longer looks healthy while the scheduler is already gone.

### Build

- The API allocation now copies capability packs into the process tree, so Build can
  see that terraform declares an authoring workflow. Without that copy every Build was
  refused as undeclared.
- A finished Build that opened a pull request now shows the link. Publish wrote the
  URL but left the run unmarked, so the page reported "Ended without a pull request."

### Portal

- Ask and Build share one dark conversational shell (icon rail, per-verb list, thread,
  one-row centred composer). Inter and IBM Plex Mono replace the previous type stack; the
  light theme is withdrawn. In-flight Build shows the stored opening message when the
  platform already holds it (`intake_message` on `GET /runs/{run_id}/result`), and does
  not offer a second propose from that page.
