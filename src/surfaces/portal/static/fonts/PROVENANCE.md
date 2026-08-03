# Provenance — Roboto, vendored for the portal

**This font was not written here.** It is adopted from upstream under the same discipline
ADR-0004 applies to the Terraform skills: a font entering this tree is third-party content,
and it carries a pin, a licence, digests and a review like anything else. A font is not
exempt for being a font.

## Where it came from

| Field | Value |
| --- | --- |
| Distribution repository | [`google/fonts`](https://github.com/google/fonts) |
| Commit | `2796410152d4f9524b68ed46e69c1b60f8e0f7c3` (2026-07-31) |
| Upstream path | `ofl/roboto/Roboto[wdth,wght].ttf` |
| Design source | [`googlefonts/roboto-3-classic`](https://github.com/googlefonts/roboto-3-classic), as recorded in that path's `METADATA.pb` |
| Licence | **SIL Open Font License 1.1** — `OFL.txt`, copied verbatim beside the font |
| Retrieved | 2026-08-03 |

## The licence is OFL, not Apache-2.0 — and the planning artifacts said otherwise

034's spec, plan and tasks each recorded "Apache-2.0 — the same licence as this repository."
**That was wrong**, and it was wrong in the plausible direction: Roboto *was* Apache-2.0 for
years before the Google Fonts collection moved to OFL 1.1, so the assumption was stale rather
than invented. It was caught here, at vendoring, by reading `OFL.txt` instead of trusting the
plan — which is the entire reason this discipline exists. The artifacts were corrected in the
same change that added this file.

**What OFL 1.1 requires of us, and what we do about it:**

- The licence travels with the font — `OFL.txt` is vendored beside it, unmodified.
- **No Reserved Font Name is declared.** The copyright line reads *"Copyright 2011 The Roboto
  Project Authors"* with no `with Reserved Font Name` clause, so OFL's rename obligation for
  Modified Versions does not bite. Recorded because its absence is what makes format
  conversion and any future subsetting unencumbered — a reader should not have to re-derive
  that.
- The font is not sold on its own, and is distributed only as part of this software.

## What was taken, and what was done to it

**One file: the variable font.** Upstream no longer ships static Regular/Bold — the directory
holds `Roboto[wdth,wght].ttf` and its italic, nothing else. The variable font carries weights
100–900 on the `wght` axis (default 400) and `wdth` 75–100 (default 100), so a single file
covers every weight the portal asks for, and there is one digest to verify rather than two.

**Italic is not vendored.** The upstream italic is a second 519 KB file for one use — the
window note — and the browser's synthetic oblique is adequate there. Recorded rather than
silently omitted so nobody wonders whether it was forgotten.

**The only modification is the container format**, TTF → WOFF2. Glyph data, metrics and name
table are untouched; this is the same transformation Google Fonts itself performs to serve the
family, and it is not a Modified Version in OFL's sense. Reproduce it with:

```sh
uv run --with fonttools==4.63.0 --with brotli python -c '
from fontTools.ttLib import TTFont
f = TTFont("Roboto[wdth,wght].ttf"); f.flavor = "woff2"; f.save("roboto-variable.woff2")'
```

## Digests

Verified by a row in `tests/component/test_portal_identity.py`, which recomputes them — the
row is the verifier, exactly as the pack loader is for skill bytes.

| File | sha256 |
| --- | --- |
| Source `Roboto[wdth,wght].ttf` (upstream, not vendored) | `d7598e12c5dbef095ff8272cfc55da0250bd07fbdecbac8a530b9b277872a134` |
| `roboto-variable.woff2` (vendored, 222,632 bytes) | `503621f33ee03dbd34032049ee54c0e95889ccf901e05ce9939a91245d16285f` |
| `OFL.txt` (vendored verbatim) | `061402327a96aadb0bfb694a960ed289ecd38d383e396243831ab81feb109c41` |

The source digest is recorded although the file is not vendored: it is what makes the
conversion reproducible end to end, so a future reader can re-derive our woff2 from upstream
bytes and compare rather than taking this document's word for it.

## Size, stated rather than buried

222 KB, served once and cached. The plan estimated ~90 KB for two static weights that upstream
no longer publishes; the variable font is larger and covers every weight instead of two. It is
served from the portal's own origin — no CDN, no runtime third-party fetch — and
`font-display: swap` means text is readable before it arrives. If the size ever matters,
subsetting to Latin is available and unencumbered (no Reserved Font Name); it is not done now
because it would add a modification step to verify for a portal that is not on a hot path.

## Review

Read at vendoring on 2026-08-03: `OFL.txt` in full (licence terms, absence of a Reserved Font
Name) and the font's axis and name records via `fontTools`. A font carries no instructions to
an agent, so ADR-0004's injection lens has no purchase here — what it is checked for instead
is that it is the thing it claims to be, from the source it claims, under the licence it
claims. It is.
