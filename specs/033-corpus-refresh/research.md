# Research: The corpus refresh

Every finding below is measured against the tree or against a decision already on record.
Nothing here re-opens 024's sync mechanics.

## F1 — Where the timestamp lives, and its shape

**Decision**: `synced_at` as an ISO-8601 UTC string in `corpus/manifest.json`, top-level,
beside `corpus_digest`. Written by `corpus_sync.py` at the moment the manifest is composed.

**Rationale**: the manifest is already the pin's identity document and already the thing a
review diffs. A sidecar file would be a second thing to keep in step; a git-log-derived time
would make the age depend on repository surgery (squashes, rebases) rather than on the sync.

**Alternatives considered**: git commit time of the manifest (rejected — rewritten history
rewrites your provenance); a separate `corpus/sync.json` (rejected — two files, one fact).

## F2 — The loader's posture toward the timestamp

**Decision**: `Corpus.synced_at: datetime | None = None`. The loader parses the field if
present and well-formed; absent, unparseable, or **in the future** all load as `None`. No
exception path exists for a bad timestamp.

**Rationale**: FR-002 and the fail-closed principle pull the same way here, and it is worth
saying why this is not a fail-open: the failure being guarded is *an answer claiming
currency it does not have*. Loading `None` and disclosing "age unknown" fails toward MORE
disclosure, not less. A loader that crashed on a malformed date would take answering down
over metadata — the 024 corpus (no timestamp at all) must keep answering the day this lands.

**Future timestamps**: clock skew at sync produces one; a negative age is nonsense and a
"fresh" reading would be unearned. Unknown, with the note saying so.

## F3 — The note is composed where the window note is composed

**Decision**: a new pure function `describe_ground(synced_at, now)` in
`core/answering/ground.py`; `surfaces/api/ask.py` calls it beside `describe_window` and puts
the result on `Answer.ground_note` (new field, `""` default). The API serializes it in the
guidance payload exactly as it serializes `window_note` in the estate payload; the portal
template renders it in the same meta block; the MCP surface inherits it through the proxied
payload.

**Rationale**: 029 already litigated where disclosure rides (the answer object, never a
sealed-core event) and how it reaches three surfaces (one shared payload). Consuming that
shape is Principle VII working; inventing a second channel would be the fragmentation the
principle names. `now` is injected by the caller, which is what makes the tier rows testable
at fixed times — the same pattern the volume rows adopted after the midnight-CI failure.

**Alternatives considered**: composing in `answer_question` itself (rejected — the core
function has no clock and should not grow one; the surface owns "when is now", exactly as it
does for the estate window).

## F4 — Tier constants and wording

**Decision**: `GROUND_FRESH_DAYS = 30` and `GROUND_STALE_DAYS = 90` in `ground.py`, the only
place they exist. Four wordings: plain age (< 30d), aging (30–90d), stale with a refresh
suggestion (> 90d), and unknown. The wording states the pinned date and the age in days —
the reader gets the fact, the tier only tunes the framing. The note never suppresses itself:
a one-day-old pin still discloses, because SC-001 says every answer, and a note that appears
only when things are bad trains readers that silence means fresh — which is exactly the
unfounded claim this feature removes.

## F5 — The weekly proposal's mechanics

**Decision**: `.github/workflows/corpus-refresh.yml`, `schedule: cron` weekly plus
`workflow_dispatch` for manual runs. It runs `corpus-sync` and `skills-provenance`, and if
`git status` shows changes (a timestamp move counts), opens a PR with `gh pr create` using
the workflow's default `GITHUB_TOKEN`. Branch name carries the date; an existing open
refresh PR is updated, not duplicated.

**Rationale**: the repo's CI is GitHub Actions (ci.yml, enclave.yml measured present); the
sync is already a committed-artifact producer, so "prepare a reviewable change" is exactly
`git commit` + `gh pr create`. The workflow is not a gate and no gate depends on it —
FR-004's hermeticity is untouched because the only fetching code runs in a non-blocking,
scheduled context.

**Failure posture (FR-007)**: the sync script's existing behavior — die before writing on
fetch or redaction failure — means a failed run leaves the tree clean, no PR opens, and the
workflow run itself is red in the Actions tab, which is where the maintainer already looks.
A red scheduled run IS the visibility; the pin is untouched by construction.

## F6 — The vendored skills' provenance is pack.toml's, not markdown's

**Decision**: machine-readable provenance joins `packs/terraform/pack.toml` —
`[skills.provenance]` with `source_repo`, `source_commit`, `retrieved` — written by a new
`infra/bin/skills-provenance` helper that compares the recorded commit against upstream
`hashicorp/agent-skills` HEAD (a git ls-remote, no clone needed for the no-change case).
`PROVENANCE.md` stays exactly what it is: the human review record, including the
injection-lens review, which no script regenerates.

**Rationale**: the human document already carries commit + retrieved date, but prose is not
a seam — the loader and the rows need fields. The digests over skill bytes already live in
pack.toml, so provenance beside them keeps *what* and *where-from* in one reviewed file.

**The bump path is not bypassed**: if upstream moved, the helper does NOT vendor the new
content. It reports the drift in the proposal (recorded commit vs upstream HEAD), because
adopting changed content is a reviewed act through the existing promotion/injection lens —
ADR-0004's first-import review for new files, `promote_skill()` for bumps. The weekly
proposal makes the drift visible; a human makes it land. This is narrower than "sync the
skills" and that narrowness is the design: F5's PR can say "upstream moved, here is the
diff to review", never "here is new third-party content, pre-merged".

## F7 — The vault skill is outbound and the sync must refuse it

**Decision**: `skills-provenance` operates only on packs whose pack.toml declares a
provenance source. `packs/vault/skills/vault-secret-access` was AUTHORED here (013) and is
intended as an upstream PR — it has no source to sync from, and a helper that "refreshed" it
from upstream would overwrite our own authorship with whatever name-collides there. The
helper refuses packs without a declared source, naming the reason.

**Rationale**: measured — vault skills have no PROVENANCE.md because there is no provenance;
the memory record from 013 says upstream-bound. The distinction (inbound-vendored vs
outbound-authored) is load-bearing and this feature writes it down where the mechanism reads.

## F8 — What the conformance rows must pin (the drift traps, named up front)

- The note appears on EVERY guidance answer payload, all three surfaces — asserted through
  the full ask path and the served MCP proxy row, not by reading `ask.py`.
- The tier boundaries fire on the boundary days exactly (29/30/89/90/91 fixture times) —
  off-by-one wording is invisible without boundary rows.
- The workflow YAML invokes exactly `infra/bin/corpus-sync` and `infra/bin/skills-provenance`
  — a prose-matching row using the shared stripper, because five prior features found gates
  matching comments instead of code.
- The 024-shaped manifest (no `synced_at`) loads and answers with the unknown wording — the
  backward-compatibility row that lets this feature merge before the first re-sync.
- No blocking lane gains network access: the existing no-fetch posture rows must stay green
  with the new module imported.
