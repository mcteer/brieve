# Quickstart: validating the portal's visual identity

Prerequisites: `uv sync --extra adapters --extra surfaces --extra portal --extra a11y` and
`uv run --extra a11y playwright install chromium`. No enclave, no credential, no network
beyond the one-time browser install.

## 1. The doubled gate (US1 + US3)

```sh
uv run --extra adapters --extra surfaces --extra portal --extra a11y pytest tests/a11y -q
```

Expected: every row runs twice — once per theme — and passes. The row count roughly doubles
against main; a dark-only failure names the theme in its id.

## 2. The identity is enforceable

```sh
uv run --extra adapters --extra surfaces --extra portal pytest tests/component/test_portal_identity.py -q
```

Expected: token discipline (no colour outside the token blocks), greyscale-surviving
dispositions, font digests matching PROVENANCE.md, no third-party URL in the stylesheet or
templates.

## 3. Look at it (the part no row can do)

```sh
DEV_IDP=1 infra/bin/portal-up      # then open the printed URL and sign in
```

Walk: thread list → a thread with turns from both packs (stripes on turns, none on the list)
→ ask a question (serif heading, Roboto prose, mono citations, the ground note in its
provenance block) → a refusal page → delete confirmation. Flip the OS appearance setting and
walk it again in dark.

## 4. The packs field

```sh
uv run --extra adapters --extra surfaces --extra portal pytest tests/conformance/api -k definitions -q
```

Expected: the view carries `packs`; a definition whose packs cannot be resolved shows `()`;
both transports serve the same view by construction.

## 5. Nothing else moved

```sh
make check && uv run --extra adapters --extra surfaces --extra portal pytest -m "not enclave" -q
```

Expected: green; no route changed, no payload beyond the one additive field, the portal still
serves offline.
