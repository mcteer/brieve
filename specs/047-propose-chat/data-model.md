# Data model: Propose chat (047)

## ProposeSubmission

| Field | Meaning |
| --- | --- |
| `correlation_id` | Joins intake → phases → tools → PR |
| `tenant_id` | Must match run tenant |
| `requester` | Subject user id |
| `target_repository` | Normalized forge id / URL form used for ownership + clone |
| `task` | Natural-language ask |
| `pack` | Authoring pack (`terraform` for this feature’s product shape) |

Maps onto `AuthoringRequest` after URL normalization and pack selection.

## PhaseName

Ordered enum (stable wire strings):

1. `research`
2. `plan`
3. `write`
4. `judge`
5. `propose`

## PhaseState

| Field | Meaning |
| --- | --- |
| `name` | PhaseName |
| `status` | `pending` \| `active` \| `completed` \| `failed` |
| `reason` | Optional user-safe string; required when `failed` for display |

Invariant: at most one `active`; no phase after a `failed` may be `completed` or `active`.

## ProposeProgress

| Field | Meaning |
| --- | --- |
| `phases` | Ordered list of PhaseState (all five names always present once started) |
| `current` | Name of active phase, or null if terminal |

Exposed on run view / result for SSE consumers.

## ProposeOutcome

| Disposition | Meaning |
| --- | --- |
| `complete` | `pr_url` present; bounded `plan_evidence` summary optional/accompanying |
| `ended_without_result` / refused | `failed_phase` + `reason`; no `pr_url` as success |

## OwnedRepositorySet

Deployment-configured frozenset of repository identifiers the requester may propose into.
Not inferred from installation alone (installation is shared; ownership check bounds the
requester — existing authoring rule).
