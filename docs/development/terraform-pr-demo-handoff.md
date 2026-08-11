# Terraform PR workflow demo — handoff notes

**Created:** 2026-08-11  
**Purpose:** Persistent context for continuing work on a **Terraform change-proposal demo**
(author → real `terraform plan` gate → PR with plan evidence) on a different machine.

**Related:** [ROADMAP.md](../../ROADMAP.md) section *"The change-proposal workflow, end to end"*
(unnumbered). Vault policy authoring (042) is the template; Terraform is the named target workflow.

---

## Goal

Present a **demo of a Terraform PR workflow**:

1. User/operator declares a target Git repo and task
2. Agent reads existing Terraform via `read_subject`
3. Agent authors changes via `author_file`
4. **`terraform plan`** runs against the authored tree (must be **real**, not a fixture)
5. Failed plan → **no PR**; successful plan → plan output attached as evidence
6. **`open_proposal`** opens a PR whose body includes diff summary, bounded plan output, and
   citations to pinned Terraform guidance (same pattern as Vault's `compose_policy_evidence`)

Secondary interest: answer **usefulness** (true/cited/on-subject but useless) — improves demo
narrative via corpus citations in PR rationale, but **not blocking** the Terraform PR story.

---

## Platform state (as of 2026-08-11)

### Merged and usable (after stack is up)

| Area | Status |
|------|--------|
| Portal Ask + Run an agent | PR [#196](https://github.com/mcteer/brieve/pull/196), commit `18f215a` on `main` |
| Local stack | `deploy/local/stack.sh up` — Nomad enclave + dev-idp + MCP + portal |
| Portal URL | https://127.0.0.1:8082/ |
| Admin console | `/settings` (044) — bindings, judge toggle, claim mappings, connections |
| Customer Git context | Endorse → sync → cite (045 Git half) |
| Authoring spine | `read_subject`, `author_file`, `open_proposal` (038/041) |
| Vault policy PR demo | 042 + `tests/evals_live/policy_authoring_e2e.py` (PL2) — **template to copy** |

### Local environment notes

- Portal/API copy `src/` at **allocation start** — code changes need allocation restart
  (`nomad alloc restart <portal-alloc>` or redeploy).
- Stack was **partially down** when last checked: Nomad down, Postgres down, dev-idp container
  still up on `:8090`. Bring back with `deploy/local/stack.sh up`.
- Git on `main` should be clean at `18f215a` after Cursor restart (refresh Source Control if stale).

### Not usable yet for Terraform demo

| Gap | Today |
|-----|--------|
| `terraform_plan` / `terraform_apply` | **Fixtures** in `src/surfaces/handlers.py` |
| Plan as gate | Not implemented |
| Plan evidence in PR | Proposals don't carry plan evidence |
| Terraform in authoring allocations | Authoring image has git/gh, not Terraform CLI + backend |
| One-button dispatch | Analyzer→proposer checkpoint incomplete; no user intake surface |
| Authoring ceiling | `authoring-agent` tools: `read_subject`, `author_file`, `open_proposal` only |

---

## What already exists (copy these patterns)

### Vault policy PR (042) — primary template

- Dispatch: `src/surfaces/dispatch/policy_authoring.py` — `compose_policy_evidence()`
- Live script: `tests/evals_live/policy_authoring_e2e.py` — uses production modules end-to-end
- Flow: acquire subject → author → **measure with Vault** → compose → publish PR

### Authoring platform (038/041)

- Tools: `src/core/authoring/tool.py`, `src/core/authoring/publish.py`
- Two-task tier: `infra/jobs/authoring-tier.nomad.hcl` (analyzer prestart + proposer `RUN_CONTINUE`)
- Module assignment: `src/core/authoring/__init__.py` docstring
- Dev definition: `infra/environments/dev/variables.tf` (`authoring-agent`)

### Terraform pack (metadata only for authoring today)

- `packs/terraform/pack.toml` — declares `terraform_plan` / `terraform_apply`
- Probe is fixture: `src/surfaces/probes.py`
- No pack workflow hooks for Terraform authoring yet

### Known integration gaps (from exploration)

- `prepare_authoring_run` in `src/surfaces/dispatch/authoring_dispatch.py` — **no production caller**
- `proposal_payload` / checkpoint handoff — **`evidence` may not round-trip** to proposer
  (`src/surfaces/dispatch/authoring.py`, entrypoint)
- `POST /runs` dispatches generic `agent-run`, not `authoring-tier` with `AuthoringRequest` payload
- No numbered spec for Terraform change-proposal yet (ROADMAP entry is unnumbered)

---

## Minimum viable demo scope

### Can defer for first demo

- Portal intake UI (operator/script supplies repo + task)
- Multi-tenancy (ADR-0046)
- Multiple plan iterations in one run (one final plan as gate is enough)
- `terraform_apply` (stay off authoring ceiling per 038)
- Full Nomad dispatch wiring (script can call production modules like PL2)
- MCP-server customer doc sources (045 half)

### Must be real for credible demo

- **`terraform plan`** against authored tree (ADR-0047 / ROADMAP: fixture gate is unacceptable)
- Real **`author_file`** writes and PR diff
- **Plan evidence in PR body**
- **Real GitHub PR** (already proven in 041)
- **Failed plan blocks publish**
- **Bounded/redacted plan output** (no secrets in model context or PR)

### Fastest path

Clone `policy_authoring_e2e.py` → `terraform_authoring_e2e.py` using production
`acquire_subject`, `FileAuthor`, `compose`, `ProposalPublisher`, plus new plan handler and
`compose_plan_evidence()`. Does **not** require full entrypoint wiring for first room demo.

---

## Recommended work order

### Phase 1 — Demo MVP (script + real plan)

| # | Work | Paths / notes | Size |
|---|------|---------------|------|
| 1 | **New spec** (046 or next number): plan gate, evidence-in-PR, bounded output | `specs/046-terraform-change-proposal/` — required before merge per AGENTS.md | L |
| 2 | Real **`terraform_plan` handler** (subprocess, structured result, fail-closed) | `src/surfaces/handlers.py` + conformance tests | M–L |
| 3 | **`terraform_authoring.py`** — `compose_plan_evidence()`, plan gate | `src/surfaces/dispatch/` (mirror `policy_authoring.py`) | M |
| 4 | Fix **proposal checkpoint** — `evidence` round-trip | `src/surfaces/dispatch/authoring.py`, `entrypoint.py` | S |
| 5 | Extend **authoring ceiling** with `terraform_plan` | `infra/environments/dev/variables.tf` | S |
| 6 | **Live demo script** | `tests/evals_live/terraform_authoring_e2e.py` | M |
| 7 | **Infra minimum** — Terraform CLI in authoring alloc or host for script; demo backend | `infra/jobs/authoring-tier.nomad.hcl`, dev vars | L |

Suggested sequence: **1 → 2 → 3 → 6** (script proves story), then 4–7 for platform hardening.

### Phase 2 — Platform demo (after Phase 1)

- Analyzer orchestration: author → plan → compose → checkpoint in entrypoint
- Wire `prepare_authoring_run` + `authoring-tier` + `subject_path` meta in `nomad.py`
- Minimal API/portal intake (repo + task)
- Conformance rows + portal polish

---

## Open decisions (pick when resuming)

1. **Demo repository** — small owned repo where `terraform init` / plan works
2. **Real cloud vs self-contained** — null provider / local state for first showing vs AWS/etc.
3. **Spec first vs spike in parallel** — AGENTS.md requires spec PR before implementation merge;
   spike (handler + script) can run in parallel with `/speckit-specify`

---

## Commands reference

```bash
# Local stack
deploy/local/stack.sh up
deploy/local/stack.sh status

# Checks
make check

# Vault policy demo (reference)
make dev-up
E2E_TARGET_REPOSITORY=owner/repo E2E_POLICY_PATH=path/to/policy.hcl \
  VAULT_TOKEN=... python tests/evals_live/policy_authoring_e2e.py

# Portal
open https://127.0.0.1:8082/
```

---

## How to resume in Cursor

Paste or say:

> Continue from `docs/development/terraform-pr-demo-handoff.md` — Terraform PR workflow demo.
> Goal: Phase 1 MVP (real plan handler + E2E script modeled on policy_authoring_e2e.py).

---

## Roadmap context (not blocking demo)

Scheduled **Next** after this composition feature:

- **Multi-tenancy** (ADR-0046) — do later unless needed for demo
- **Customer context MCP/API sources** (045 other half)
- **Answer usefulness** — unnumbered ROADMAP item; separate from Terraform PR gate

**Parked / not building:** code mode in production (ADR-0065), 016 task-scoped authority (ADR-0057).
