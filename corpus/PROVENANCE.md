<!-- SPDX-License-Identifier: Apache-2.0 -->
# The guidance corpus, and why it is pinned rather than vendored

**What it is**: HashiCorp's Validated Patterns — 33 tutorials across Boundary, Nomad, Packer,
Terraform and Vault, under `https://developer.hashicorp.com/validated-patterns/`.

**Pinned on**: 2026-08-01. Corpus digest recorded in `manifest.json`.

## Why there is no content here

024's plan said to vendor the corpus the way `packs/terraform/skills/` vendors upstream skills.
That precedent works because those skills come from a repository whose licence permits it.

**Not because redistribution is prohibited — because it could not be established that it is
permitted, and this repository's own standard is higher than that.**

What was checked: the validated-patterns index and a product page carry **no statement about reuse
or redistribution**. Under default copyright, absence of a grant means no redistribution right —
but silence is not proof of prohibition, and saying "cannot be vendored" would overstate what was
found.

What could not be checked: whether the tutorials live in a public repository with a licence. The
GitHub API returns 403 for the whole `hashicorp` organisation under SAML enforcement, so the one
check that would settle it was closed.

**The deciding factor is the precedent already in this tree.** `packs/terraform/skills/` vendors
upstream content and carries **MPL-2.0 copied verbatim**, with the licence named in its provenance.
That is the bar: vendor when you hold a licence. No licence was in hand here, so the bar was not
met — which is a different and smaller claim than "it is not allowed".

**If the licence question later resolves in favour of vendoring, that is an addition rather than a
correction.** The digest pin stands on its own merits either way: FR-014 asks for content-based
change detection because the corpus carries no version metadata, a digest *is* exactly that, and it
is a stronger pin than a copy — a vendored copy drifts from upstream silently, a digest mismatch is
loud.

## What replaces it

**A manifest, and the manifest is the pin.** For each document: its URL, a SHA-256 of its content,
and the section anchors a citation can resolve to. The content itself is fetched into
`.corpus-cache/` — gitignored — by `infra/bin/corpus-sync`.

**This satisfies FR-014 exactly.** The requirement was content-based change detection, because the
corpus carries no version metadata anywhere. A digest *is* that, and it is a stronger pin than a
copy: a copy can drift from upstream silently, while a digest mismatch is loud.

**Nothing is fetched at answer time.** That is what the plan rejected, and it stands — answering
reads the local cache and verifies it against this manifest. A cache that does not match is a
refusal, not a silent fallback.

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
