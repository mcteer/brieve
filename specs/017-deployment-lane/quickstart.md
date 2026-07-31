# Quickstart: validating 017 deployment lane

How to run this gate and how to prove it can fail. The second half matters more — a gate
nobody has seen fail is a gate nobody knows works, which is the whole thesis of the feature.

## Prerequisites

- A local enclave: `make dev-up`
- The Nomad CLI on `PATH` (already required by bring-up)
- `.env` with the enclave's coordinates, as bring-up writes it

No identity-provider credentials are needed. The assertions are refusals, deliberately —
see [contracts/conformance.md](contracts/conformance.md).

## Run it

```bash
make dev-up                 # if the enclave is not already up
bash infra/bin/deployment-conformance
```

Expected: each declared process reaches a working state within its own wait, and each
assertion reports what it observed rather than only that it passed.

The same script is what the CI lane invokes after `make conformance`. There is one way to
run this gate (Principle VII); if the two ever diverge, the one nobody runs locally is the
one that rots.

## Prove it can fail — the part that is not optional

### 1. A surface whose assembly cannot obtain its credentials

The defect the feature exists for. Submit the API pointed at a Vault role that does not
exist:

```bash
nomad job run -detach -var="repo=$PWD" \
  -var="oidc_issuer=..." -var="oidc_jwks_uri=..." \
  infra/jobs/api.nomad.hcl        # with VAULT_ROLE altered to a non-existent role
```

Expected: the gate fails, names the API, and reports the surface's own error — the login
refusal naming `nomad_job_id`, not a bare timeout. **If it reports only a timeout, FR-004 is
not met**, and the row needs the allocation's own output rather than the assertion's.

Restore with a normal submit afterwards.

### 2. A process that is running but assembled nothing

The SC-002 case, and the one a naive implementation misses. Any check that stops at
"the port is open" passes here.

Expected: the gate fails. If it passes, the assertion is a liveness check wearing this
feature's name.

### 3. A declared process with no assertion

Add a `meta` declaration to a job definition and run the gate without writing an assertion
for it.

Expected: the gate fails for not knowing how to cover it (FR-005) — not a skip, not a
warning.

### 4. The reverse: an assertion against an undeclared process

Remove a `meta` declaration and leave its assertion in place.

Expected: the gate fails. An assertion against something the deployment no longer runs
passes forever while testing nothing, which is the failure mode this whole feature is about.

## Verify it runs where it must

**Both substrates, same verdict** (FR-008, Principle VII). Run the script on macOS and on a
Linux runner against the same tree; the verdict must match.

The trap this guards: both surfaces use host networking, so on a Linux runner a shell
reaches `127.0.0.1:8081` and on Docker Desktop for macOS it does not — the "host" is the
VM. Verified on 2026-07-31: `curl http://127.0.0.1:8081/runs` returned nothing from the
developer's shell while the same request from inside the allocation returned
`401 absent_identity`.

**If a row ever reaches a surface directly from the shell, it will pass in CI and fail
locally for a reason having nothing to do with the tree.**

## Verify it did not break what already works

```bash
make conformance
```

Every merge-blocking row that ran before this feature must still run (FR-007, SC-005). The
specific risk is placement: `infra/bin/portal-up`'s header records that registering these
surfaces at bring-up *"left the conformance job unplaceable, so the merge-blocking
durability rows never ran."* The design avoids this by sequencing — the surfaces go up after
the conformance batch job releases its reservation — so the check is that the durability
rows still execute, not merely that the gate is green.

Confirm the row count did not drop. A lane that silently stopped collecting a directory is
the failure 010 paid for, and it looks exactly like a pass.

## Confirm the waits are measured, not guessed

The per-process waits are a measurement. Run the gate on the CI runner cold, observe each
process's start time, and set each wait well above it. A wait set from a guess fails on the
first cold cache and reads as a broken surface.
