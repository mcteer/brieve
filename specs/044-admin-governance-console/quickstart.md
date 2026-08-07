# Quickstart: The admin console

How to see it working, cheapest first. Row IDs refer to
[contracts/conformance-console.md](contracts/conformance-console.md).

## Prerequisites

- Hermetic: nothing beyond the repo.
- Live legs: `make dev-up`; the trust-fabric apply that ships the `authority_submit` grant
  (R1 — before it, the request-and-decide mechanism has no deployed principal) and the
  `controlled_paths` extension; a person mapped to `admin` via the gated mappings route.
- Portal: `make portal-up`, sign in as that person.

## 1 — Hermetic proof (every PR)

```sh
make check                 # C6 scan, outcome mapping, toggle semantics, role disjointness
make conformance-hermetic  # C1–C26: the write path, the reads, the exclusion, the connections
make a11y                  # CL3 — /settings is walked, not merely shipped
```

Observed 2026-08-07: `make check` 1388, `make conformance-hermetic` 667, `make a11y` 72.

Failures worth causing on purpose: collapse pending into applied (C2 fails); grant `admin`
audit visibility (C14 fails); remove the dispatched-run exclusion (C20 fails — the safety
case losing is the demonstration).

## 2 — The mechanism has a principal (live; named runner: Dan)

```sh
export VAULT_ADDR=https://127.0.0.1:8200
export VAULT_CACERT="$PWD/.enclave/ca.pem"   # the enclave serves TLS from its own CA
export VAULT_TOKEN=...                       # VAULT_ROOT_TOKEN from .env
```

**`VAULT_CACERT` is not optional and urllib will not find it for you** — that is a Vault CLI
convention, not a Python one. Without it every request fails verification and surfaces as
`URLError`, which reads as "Vault is down" rather than "the certificate was never loaded".

Confirm the grant landed before anything else, because everything below assumes it:

```sh
vault read -format=json auth/nomad/role/api | jq -r '.data.token_policies[]'
# ... must include authority-submit
```

CL1: from the console, rebind the relevance judge or flip the gate.

- **Dev estate (quorum null)**: the change applies immediately and the console says
  **ungated** — FR-007's disclosure, not an approval that never happened.
- **With a quorum configured**: the same change reports **awaiting approval**, alters nothing,
  and takes effect when approved in Vault. Pending is visibly not applied (C2, live).

## 3 — The toggle, end to end (live)

```sh
make dev-up && DEV_IDP=1 make mcp-surface-up
```

**Check the allocation is younger than your last commit.** `mcp-surface-up` submits the job,
and Nomad places no new allocation when the jobspec has not changed — so a running process can
be hours older than the code you are testing. `nomad job status mcp-surface` shows its age;
`nomad alloc stop <id>` replaces it. The tell is an **absent** field in the response rather
than an empty one: empty means the code ran and found nothing, missing means the code that
adds it is not there.

CL2: disable LLM-as-a-judge in the console; ask the answering surface a question that would
have been judged. Expected: the answer arrives **carrying the disclosure**; its record says
`relevance_disabled_by_admin`, not `relevance_unavailable`; no `MODEL_GATE` event exists for
it. Re-enable; the next ask judges. No process restarted at any point.

## 4 — What an administrator cannot do

- Grant themselves `admin` (C21 — refused in every wording).
- See audit evidence by virtue of the role (C14 — disjoint, Q2).
- Enter a credential anywhere (C25 — the record vocabulary has no field for one).
- Reach any of it from MCP or as a dispatched run (C19/C22).

## 5 — What did not change

- Terraform still writes every record it wrote; provenance shows which writer was last (C7's
  CAS + `set_by`).
- The approval mechanism is Vault's Control Groups, unchanged — the console shows pending,
  never approves.
- ADR-0039's vocabulary: presented with descriptions, not widened (R7).
- The answering path with the toggle enabled: byte-for-byte 043's gate.
