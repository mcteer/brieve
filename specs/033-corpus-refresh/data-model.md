# Data model: The corpus refresh

Three records, all additive, none in a database. The pin is git; the note is ephemeral; the
provenance is pack metadata.

## The pin (extended)

`corpus/manifest.json` — existing fields untouched:

| Field | Type | New? | Rules |
| --- | --- | --- | --- |
| `corpus_digest` | string | no | unchanged |
| `document_count` | int | no | unchanged |
| `documents` | array | no | unchanged |
| `synced_at` | string, ISO-8601 UTC | **yes** | written by `corpus_sync.py` at manifest composition; optional on read forever (the 024 pin never gains one retroactively) |

Loader mapping (`core/answering/corpus.py`):

| Manifest state | `Corpus.synced_at` |
| --- | --- |
| well-formed ISO-8601, past | parsed `datetime` (UTC) |
| absent (the 024 pin) | `None` |
| unparseable | `None` |
| in the future (skew) | `None` |

No exception path. `None` means *unknown*, and unknown is disclosed, not hidden.

## The disclosure (new, ephemeral)

`Answer.ground_note: str = ""` — composed per answer by `describe_ground(synced_at, now)`
(`core/answering/ground.py`), serialized in the guidance payload beside the claims, rendered
by the portal, proxied by MCP. Never persisted, never on an audit event.

Tiers (constants live in `ground.py` only):

| Age | Wording carries |
| --- | --- |
| `None` | ground age unknown — the pin predates sync timestamps |
| < 30 days | pinned date + age, plain |
| 30–90 days | pinned date + age, aging framing |
| > 90 days | pinned date + age, stale framing + refresh suggestion |

State rule: the note NEVER suppresses itself and NEVER causes a decline (FR-005). The
disposition machinery is untouched.

## The skills provenance (existing pack metadata, consumed)

**No new fields** (analyze C1): `packs/terraform/pack.toml` already carries the
loader-parsed pin —

```toml
[upstream]
repository = "https://github.com/hashicorp/agent-skills"
commit     = "8c6573abbd21e8094fab8f538eb5f97db63133fd"
licence    = "MPL-2.0"
retrieved  = "2026-07-29"
```

— required for adopted packs and parsed into `UpstreamPin` by `src/core/packs/loader.py`.
The helper reads it and updates only `retrieved`.

| Rule | Enforcement |
| --- | --- |
| `provenance = "adopted"` ⇒ `[upstream]` exists (loader-enforced) ⇒ eligible for the weekly drift check | `skills-provenance` operates on adopted packs only |
| `provenance = "authored"` (vault: outbound) ⇒ refused by the helper, reason named | F7 — never "refreshed" from a name-colliding upstream |
| Upstream moved ⇒ the proposal REPORTS drift (`commit` vs upstream HEAD); content adoption stays a human act through the existing promotion/injection lens | F6 — the bump path is not bypassed |
| Skill bytes digests | unchanged, already in pack.toml, already verified at load |

## The prepared refresh (a PR, not a table)

Produced by `.github/workflows/corpus-refresh.yml` weekly or on dispatch: new manifest (+
documents if changed) + provenance updates, on a dated branch, as a PR that cannot merge
itself. A no-change-upstream run still moves `synced_at` — that diff IS the "we checked"
record. A failed sync writes nothing and leaves a red workflow run as the signal.
