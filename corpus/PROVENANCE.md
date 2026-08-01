<!-- SPDX-License-Identifier: Apache-2.0 -->
# The guidance corpus, and why it is pinned rather than vendored

**What it is**: HashiCorp's Validated Patterns — 33 tutorials across Boundary, Nomad, Packer,
Terraform and Vault, under `https://developer.hashicorp.com/validated-patterns/`.

**Pinned on**: 2026-08-01. Corpus digest recorded in `manifest.json`.

## Vendored, and why

The content is here — 33 documents, as extracted sections under `documents/`.

**An earlier version of this file pinned by digest only and left the content out**, on the grounds
that the pages state no licence and this repository's precedent (`packs/terraform/skills/`, MPL-2.0
copied verbatim) is to vendor only with a licence in hand. The maintainer's call was that these are
publicly accessible pages and this is a HashiCorp-endorsed project — context the caution did not
have. Recorded rather than quietly reversed, because the reasoning is worth finding if the question
comes up again.

**Sections, not markup.** Thirty-three pages of raw HTML is roughly fourteen megabytes of
navigation, scripts and styling, none of which an answer cites. What a citation points at is a
section, so a section is what is stored: anchor, heading, and text.

## The manifest is still the pin

Two different questions, kept separate:

- **`manifest.json` digests the upstream page.** It answers *did HashiCorp change this* — the only
  way to ask, since the corpus carries **no version metadata anywhere**. This is what FR-014 wants,
  and it is a stronger signal than a copy on its own: a vendored copy drifts from upstream
  silently, a digest mismatch is loud.
- **Loading verifies the vendored content.** Every anchor the manifest names must exist in the
  document committed beside it. A citation resolving against a pin whose content is absent would be
  a citation to nothing.

**Nothing is fetched at answer time.** `infra/bin/corpus-sync` refreshes both; answering reads only
what is committed.

## Verified on arrival (T004a)

Three properties the design depends on, all carried from prior context and none checkable from this
repository until now:

- **33 documents** — confirmed. Boundary 1, Nomad 1, Packer 4, Terraform 12, Vault 15.
- **Stable per-section anchors** — confirmed. Every document exposes heading anchors; the manifest
  records them per document, so an unresolvable citation is detectable without a network call.
- **No version metadata anywhere** — confirmed. Neither the index nor the documents carry a
  version or a last-updated date, which is why the pin has to be a digest.

## Refreshing

`bash infra/bin/corpus-sync` refetches and rewrites the manifest. **A changed digest is a corpus
change**, and citations must be re-verified against it — which is the point of pinning by content
rather than by a version string that does not exist.
