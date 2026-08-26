# Provenance — Roboto and IBM Plex Mono, vendored for the portal

**These fonts were not written here.** They are adopted from upstream under the same
discipline ADR-0004 applies to the Terraform skills: a font entering this tree is
third-party content, and it carries a pin, a licence, digests and a review like anything
else. A font is not exempt for being a font.

This record covers the two families the portal actually serves.

## Where they came from

| Field | Value |
| --- | --- |
| Distribution repository | [`google/fonts`](https://github.com/google/fonts) |
| Commit | `e1118da94a8cb00cf6d06cdac9ef13eb1e5c6ab7` |
| Roboto upstream path | `ofl/roboto/Roboto[wdth,wght].ttf` |
| IBM Plex Mono upstream paths | `ofl/ibmplexmono/IBMPlexMono-Regular.ttf`, `ofl/ibmplexmono/IBMPlexMono-Medium.ttf` |
| Licence | **SIL Open Font License 1.1** — `OFL-roboto.txt` and `OFL-ibm-plex-mono.txt`, copied verbatim beside the fonts |
| Retrieved | Roboto 2026-08-25; IBM Plex Mono 2026-08-17 |
| Converter | ephemeral `fonttools==4.63.0` with `brotli` (same command shape as 034) |

## Reserved Font Name

Read at vendoring from each family's `OFL.txt`:

- **Roboto — no Reserved Font Name is declared.** The copyright line reads *"Copyright 2011 The Roboto Project Authors (https://github.com/googlefonts/roboto-classic)"* with no `with Reserved Font Name` clause.
- **IBM Plex Mono — Reserved Font Name "Plex" is declared.** The copyright line reads *"Copyright © 2017 IBM Corp. with Reserved Font Name "Plex""*. TTF → WOFF2 without touching glyph data is the transformation 034 recorded as not a Modified Version, so the family name is kept.

## What was taken, and what was done to it

**Roboto: the variable font.** One file covers the weights the portal asks for (`wght` 100–900; `wdth` 75–100, default 100).

**IBM Plex Mono: Regular (400) and Medium (500).** Upstream ships static weights; those two are what evidence text uses.

**Italic is not vendored** for either family. The browser's synthetic oblique is adequate.

**The only modification is the container format**, TTF → WOFF2. Glyph data, metrics and name table are untouched. Reproduce it with:

```sh
uv run --with fonttools==4.63.0 --with brotli python -c '
from fontTools.ttLib import TTFont
f = TTFont("Roboto[wdth,wght].ttf"); f.flavor = "woff2"; f.save("roboto-variable.woff2")
f = TTFont("IBMPlexMono-Regular.ttf"); f.flavor = "woff2"; f.save("ibm-plex-mono-regular.woff2")
f = TTFont("IBMPlexMono-Medium.ttf"); f.flavor = "woff2"; f.save("ibm-plex-mono-medium.woff2")'
```

## Digests

Verified by a row in `tests/component/test_portal_identity.py`, which recomputes them — the
row is the verifier, exactly as the pack loader is for skill bytes.

| File | sha256 |
| --- | --- |
| Source `Roboto[wdth,wght].ttf` (upstream, not vendored) | `d7598e12c5dbef095ff8272cfc55da0250bd07fbdecbac8a530b9b277872a134` |
| `roboto-variable.woff2` (vendored, 222,580 bytes) | `157993441701890f9efb57c639b8f4b05f2912cb57ddd4d9c98f5d23e26eb576` |
| Source `IBMPlexMono-Regular.ttf` (upstream, not vendored) | `6a3412f058c7d8dfd9170c41e85ade48e5156ecb89356110ca57a0a27734af46` |
| `ibm-plex-mono-regular.woff2` | `8d1fd3c10dbce49fc10eb06d1cbe56e3eef7ca17cda57ec6c0c52455ea3ad172` |
| Source `IBMPlexMono-Medium.ttf` (upstream, not vendored) | `a9b4c49bb299e05b5f6c481e7fb5e78943d2793249a0c8874ab574a2d1ea6755` |
| `ibm-plex-mono-medium.woff2` | `ec573dfe0897a2ea2afd40f79a7c72018e6cdd0886f3a4d2ed3f6a758c12a713` |
| `OFL-roboto.txt` (vendored verbatim) | `061402327a96aadb0bfb694a960ed289ecd38d383e396243831ab81feb109c41` |
| `OFL-ibm-plex-mono.txt` (vendored verbatim) | `3ff4395aeb203050b3d4e775861cf0b93b598e0a6d2b16f0eb41df3350b15695` |

The source digests are recorded although the files are not vendored: they are what makes the
conversion reproducible end to end.

## Size, stated rather than buried

Roboto variable 223 KB plus two Plex weights (~79 KB) are served from the portal's own origin —
no CDN, no runtime third-party fetch — and `font-display: swap` means text is readable before
they arrive.

## Review

Read at vendoring: both `OFL.txt` files in full (licence terms, Reserved Font Name presence
or absence) and the font name records via `fontTools`. A font carries no instructions to an
agent, so ADR-0004's injection lens has no purchase here — what it is checked for instead is
that it is the thing it claims to be, from the source it claims, under the licence it claims.
It is.
