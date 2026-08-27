# Data Model: A run's write grant names only its own workspace

**Date**: 2026-08-27 | **Spec**: [spec.md](spec.md)

Three things, one of which is a record an auditor reads. Nothing here is a new store.

## Run workspace

The set of policy paths belonging to one run — today `scratch-agent-{run_id}-current` and
`-proposed`.

| Field | Meaning |
| --- | --- |
| `run_id` | The run it belongs to. Already what the names are derived from |
| `paths` | The exact paths, expanded — not a pattern with a wildcard left in it |
| `capabilities` | Per path. `create`, `update`, `delete`, `read` for the measurement case |

**Expanded, not templated, and this is the whole point.** The current grant is one pattern
covering every run. A workspace is a concrete list for one run: a wildcard surviving into it
would reintroduce the defect in the object built to remove it.

## Scoped write grant

What a run actually holds. Manufactured at run time because no apply-time artifact can name a
run that does not exist yet.

| Field | Meaning |
| --- | --- |
| `workspace` | The run workspace above. The grant may name nothing else |
| `expires` | When it stops working. Short by construction |
| `renewable_while` | The run's liveness. Renewal stops when the run does (FR-014) |

**Absent for most runs.** FR-012: manufactured only when the run's requested tools declare a
write path, so a run that will never write holds no write authority at all — stricter than
today's estate-wide grant.

## Recorded scope

The derivation, stored once and re-presented on every re-mint.

| Field | Meaning |
| --- | --- |
| `run_id` | Whose scope this is |
| `paths` | What was derived, at first manufacture |
| `derived_from` | The declared tool paths it came from, so a reader can check it |

**This is a record, not a cache.** Two requirements read it. FR-017 needs every re-mint —
resume, renewal, retry — to be scope-identical, and storing one derivation removes the drift
class rather than detecting it ([R5](research.md)). FR-011 needs an auditor to say afterwards
what a run's authority actually granted, and this is what answers.

**The hazard it exists for**, in the maintainer's words: a fresh grant on resume could be
derived differently and end up wider, which would defeat the feature while appearing to work.

## Relationships

```
pack manifest `paths` (already in tree, read by nothing — R4)
        │
        └──(derived once, at first manufacture)──> Recorded scope
                                                        │
                    ┌───────────────────────────────────┤
                    │                                   │
            Run workspace ──(names)──> Scoped write grant
                                                │
                            re-mint (resume / renewal / retry)
                            MUST reproduce, never re-derive (FR-017)
```

## What is deliberately not modelled

- **Read scope.** Untouched (FR-006). ADR-0057's argument stands.
- **The sweeper's authority.** It lists the namespace by design and keeps its breadth (FR-008).
- **A fallback grant.** There is none. Failure stops the run (FR-005, FR-015); an object
  representing "the wider grant we fall back to" would be the thing this feature removes,
  modelled.
