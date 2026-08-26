# Quickstart: validating Create home

Prerequisites: `uv sync --extra adapters --extra surfaces --extra portal --extra a11y`
and `uv run --extra a11y playwright install chromium`. No enclave for the
hermetic rows.

## 1. Designed-theme gate

```sh
uv run --extra adapters --extra surfaces --extra portal --extra a11y pytest tests/a11y -q
```

Expected: every covered state on dark; 24×24; 320px; no horizontal scroll; named
New, Projects, search, slider, Stop, +, profile, Settings, logout.

## 2. Shell and identity

```sh
uv run --extra adapters --extra surfaces --extra portal pytest \
  tests/component/test_portal_shell.py \
  tests/component/test_portal_identity.py \
  tests/component/test_portal_session.py \
  tests/component/test_portal_asks.py -q
```

Expected: `GET /` is create home (mark, Let's Create, slider on Ask);
`GET /ask` is 303 `/`; history mixes Ask and Build; search filters visible text;
Ask selected has no `action="/"`; `propose_run.html` has no `POST /`; login
without next is `/`; mark digest matches `mark/PROVENANCE.md`; no icon rail as
the only Settings path.

## 3. Look at it

```sh
bash deploy/local/stack.sh status   # portal already up: https://127.0.0.1:8082/
```

Sign in. Empty home: HashiCorp mark, Let's Create, slider on Ask. Combined
history on the left. Move the slider to Build and back. Open an Ask: title at
the top, bubble at the bottom, slider locked. Open a Build: same, Stop in the
bubble ends the run. + and Projects do nothing useful. + New returns home on
Ask. Settings and logout are at the bottom of the column. Sign out and in:
home, Ask selected.

## 4. Nothing else moved

```sh
make check
```

Expected: green; no new catalogue operation; 047 P8 still holds; portal still
serves offline.
