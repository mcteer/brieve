# Provenance — Inter and IBM Plex Mono, vendored for the portal

**These fonts were not written here.** They are adopted from upstream under the same
discipline ADR-0004 applies to the Terraform skills: a font entering this tree is
third-party content, and it carries a pin, a licence, digests and a review like anything
else. A font is not exempt for being a font.

This record covers the two families 048 actually serves.

## Where they came from

| Field | Value |
| --- | --- |
| Distribution repository | [`google/fonts`](https://github.com/google/fonts) |
| Commit | `e1118da94a8cb00cf6d06cdac9ef13eb1e5c6ab7` |
| Inter upstream path | `ofl/inter/Inter[opsz,wght].ttf` |
| IBM Plex Mono upstream paths | `ofl/ibmplexmono/IBMPlexMono-Regular.ttf`, `ofl/ibmplexmono/IBMPlexMono-Medium.ttf` |
| Licence | **SIL Open Font License 1.1** — `OFL-inter.txt` and `OFL-ibm-plex-mono.txt`, copied verbatim beside the fonts |
| Retrieved | 2026-08-17 |
| Converter | ephemeral `fonttools==4.63.0` with `brotli` (same command shape as 034) |

## Reserved Font Name

Read at vendoring from each family's `OFL.txt`:

- **Inter — no Reserved Font Name is declared.** The copyright line reads *"Copyright 2020 The Inter Project Authors"* with no `with Reserved Font Name` clause.
- **IBM Plex Mono — Reserved Font Name "Plex" is declared.** The copyright line reads *"Copyright © 2017 IBM Corp. with Reserved Font Name "Plex""*. TTF → WOFF2 without touching glyph data is the transformation 034 recorded as not a Modified Version, so the family name is kept.

## What was taken, and what was done to it

**Inter: the variable font.** One file covers the weights the portal asks for.

**IBM Plex Mono: Regular (400) and Medium (500).** Upstream ships static weights; those two are what evidence text uses.

**Italic is not vendored** for either family. The browser's synthetic oblique is adequate.

**The only modification is the container format**, TTF → WOFF2. Glyph data, metrics and name table are untouched. Reproduce it with:

```sh
uv run --with fonttools==4.63.0 --with brotli python -c '
from fontTools.ttLib import TTFont
f = TTFont("Inter[opsz,wght].ttf"); f.flavor = "woff2"; f.save("inter-variable.woff2")
f = TTFont("IBMPlexMono-Regular.ttf"); f.flavor = "woff2"; f.save("ibm-plex-mono-regular.woff2")
f = TTFont("IBMPlexMono-Medium.ttf"); f.flavor = "woff2"; f.save("ibm-plex-mono-medium.woff2")'
```

## Digests

Verified by a row in `tests/component/test_portal_identity.py`, which recomputes them — the
row is the verifier, exactly as the pack loader is for skill bytes.

| File | sha256 |
| --- | --- |
| Source `Inter[opsz,wght].ttf` (upstream, not vendored) | `29160a80ff49ddcab2c97711247e08b1fab27a484a329ce8b813d820dc559031` |
| `inter-variable.woff2` (vendored, 350,552 bytes) | `d760441abd945bb960d0960bf94a487ea3cab8dedea16fb1414cc7c6b53bdada` |
| Source `IBMPlexMono-Regular.ttf` (upstream, not vendored) | `6a3412f058c7d8dfd9170c41e85ade48e5156ecb89356110ca57a0a27734af46` |
| `ibm-plex-mono-regular.woff2` | `8d1fd3c10dbce49fc10eb06d1cbe56e3eef7ca17cda57ec6c0c52455ea3ad172` |
| Source `IBMPlexMono-Medium.ttf` (upstream, not vendored) | `a9b4c49bb299e05b5f6c481e7fb5e78943d2793249a0c8874ab574a2d1ea6755` |
| `ibm-plex-mono-medium.woff2` | `ec573dfe0897a2ea2afd40f79a7c72018e6cdd0886f3a4d2ed3f6a758c12a713` |
| `OFL-inter.txt` (vendored verbatim) | `5b9321a4298cfeb6b34354164a1c3afc3db114569984c502b9b35d988fd58c57` |
| `OFL-ibm-plex-mono.txt` (vendored verbatim) | `7e6b2818edbd8f6a01ae80641cc8f16a51080d08fb4e532be3a0b6f74adb07da` |

The source digests are recorded although the files are not vendored: they are what makes the
conversion reproducible end to end.

## Size, stated rather than buried

Inter variable 351 KB plus two Plex weights (~79 KB) are served from the portal's own origin —
no CDN, no runtime third-party fetch — and `font-display: swap` means text is readable before
they arrive.

## Review

Read at vendoring on 2026-08-17: both `OFL.txt` files in full (licence terms, Reserved Font
Name presence or absence) and the font name records via `fontTools`. A font carries no
instructions to an agent, so ADR-0004's injection lens has no purchase here — what it is
checked for instead is that it is the thing it claims to be, from the source it claims, under
the licence it claims. It is.
