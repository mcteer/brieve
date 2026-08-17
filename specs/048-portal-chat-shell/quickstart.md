# Quickstart: validating Ask and Build share one shell

Prerequisites: `uv sync --extra adapters --extra surfaces --extra portal --extra a11y` and
`uv run --extra a11y playwright install chromium`. No enclave, no credential, no network
beyond the one-time browser install.

## 1. The designed-theme gate (US1 + US4)

```sh
uv run --extra adapters --extra surfaces --extra portal --extra a11y pytest tests/a11y -q
```

Expected: every row runs once, on dark. A failure does not mention a light parametrization.
024×24, 320px reflow, and focus appearance still pass.

## 2. Identity is enforceable, and Roboto is gone

```sh
uv run --extra adapters --extra surfaces --extra portal pytest tests/component/test_portal_identity.py -q
```

Expected: token discipline (`:root` only), greyscale-surviving verdicts, composer 880px /
reading column 680px, Inter + IBM Plex Mono digests matching `PROVENANCE.md`, **no**
`roboto-variable.woff2`, no third-party URL in the stylesheet or templates, F9 comments on
`base.html` / `ask.html`.

## 3. Intake text is a field, not a guess

```sh
uv run --extra adapters --extra surfaces --extra portal pytest tests/component/test_run_result.py -q
```

Expected: a Propose-shaped run with `RunInput` returns `intake_message` equal to that
message; a run without input returns `null`; no test constructs the string inside the
assertion to satisfy it.

## 4. In-flight Build is not a second propose

```sh
uv run --extra adapters --extra surfaces --extra portal pytest tests/component/test_portal_shell.py -q
```

Expected: `propose_run.html` has no `method="post"` to `/` or `/propose`; `intake_message`
renders only inside a guard; `id="phase-strip"` and `[data-phase]` remain; phase nodes have
shape + `.phase-status` text; F9 comments on `_exchange.html` / `_outcome.html` are still
present.

## 5. Look at it (the part no row can do)

```sh
DEV_IDP=1 infra/bin/portal-up      # then open the printed URL and sign in
```

Walk: empty Build and empty Ask — same shell, composer one row, centred, verbs Ask vs Build.
Start a Build; the intake quote is on the page; phases are spine nodes, not a header meter.
Ask a question; answers sit in the same spine grammar with citations as evidence. Ask header
says never acts. Narrow the window to 320px: no horizontal scroll. Confirm Settings and
signed-out inherit the ground and type.

## 6. Nothing else moved

```sh
make check && uv run --extra adapters --extra surfaces --extra portal pytest -m "not enclave" -q
```

Expected: green; no new route; payload additive field is `intake_message` only; 047 P8 still
holds; portal still serves offline.
