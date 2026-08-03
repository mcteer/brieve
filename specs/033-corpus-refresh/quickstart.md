# Quickstart: validating the corpus refresh

Prerequisites: the repo, `uv sync --extra surfaces --extra adapters`; the enclave only for
the served-surface scenario; no vendor credential needed anywhere here.

## 1. The pin records when (US2)

```sh
uv run python infra/bin/corpus_sync.py          # against fixture upstream in tests; live if you mean it
python3 -c "import json; print(json.load(open('corpus/manifest.json'))['synced_at'])"
```

Expected: an ISO-8601 UTC time. Re-run against unchanged content: `corpus_digest` identical,
`synced_at` moved — `git diff corpus/manifest.json` shows exactly one changed line.

## 2. The answer discloses (US1)

```sh
uv run --extra adapters --extra surfaces pytest tests/component/test_ground_note.py -q
```

Expected: tier rows green at the fixture times (29/30/89/90/91 days, unknown, future). Then
the full path:

```sh
uv run --extra adapters --extra surfaces pytest tests/conformance/answering -k ground -q
```

Expected: a guidance answer through `surface_under_test` carries `ground_note`; the
024-shaped manifest (no timestamp) answers with the unknown wording.

## 3. The schedule proposes (US3)

```sh
gh workflow run corpus-refresh.yml
gh run watch                                    # the sync runs, the branch pushes
gh pr list --label corpus-refresh               # the proposal exists, unmerged
```

Expected: a PR containing the manifest diff (timestamp-only on a quiet week), skills drift
reported if upstream moved, and nothing merged. **It arrives with no CI checks** — the
default token's PRs don't trigger workflows (GitHub's recursion guard; no PAT exists by
design) — and its body says so and names the one-keystroke fix: close/reopen (or push an
empty commit) starts the checks. Close or merge it as the review it is. A merged refresh
reaches SERVED answers at the next service restart — `load_corpus` runs at start, not per
request.

## 4. Failure leaves the pin alone (FR-007)

Point the sync at an unreachable upstream (fixture): it dies before writing, `git status`
is clean, no PR opens, and the workflow run is red. Existing answers are byte-identical.

## 5. The gates never fetched

```sh
make check && uv run --extra adapters --extra surfaces --extra portal pytest -m "not enclave" -q
```

Expected: green, with the no-network posture rows unchanged — the only fetching code lives
in the scheduled, non-blocking workflow.
