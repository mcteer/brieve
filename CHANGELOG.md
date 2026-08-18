# Changelog

User-visible changes. The PR template still prompts for the entry; this file is the
durable record.

## Unreleased

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
