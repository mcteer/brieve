# Quickstart: The agent authors, and a person merges

**Feature**: 038 | **Date**: 2026-08-05

How to prove each layer works — and, for the three rows most likely to be quietly wrong, how
to prove they can **fail**. Every scenario has a conformance row behind it; see
[contracts/](contracts/).

## Prerequisites

- `uv sync --extra adapters --extra surfaces` — **no new extra**. Authoring uses `pathlib`,
  `hashlib` and `difflib`; nothing enters the tree.
- Scenarios A–E run hermetically. **Scenario F needs the `terraform` binary and a pinned
  provider mirror** (the first correctness gate — CI's gate lane, not the fast lane).
- Scenario G needs the enclave and a version-control credential path (`make dev-up`, plus
  ADR-0062's Vault-vended token). It is the only scenario that reaches a real host.

## Scenario A — A file is produced, and it is governed like anything else

```sh
uv run --extra adapters --extra surfaces pytest tests/conformance/authoring -q -k producing
```

Expected: W1–W5 pass. A write passes the same `invoke_tool` entry a read does; a definition
whose ceiling omits `author_file` is refused with the ordinary code; a program that writes a
file does so as its own governed step rather than as a side effect.

**Worth reading rather than only running: W4.** It asserts the trail carries paths and digests
and **no file content**. The artefact is a derivative of someone's private repository, and the
trail is append-only.

## Scenario B — The tier gains a subject without losing its rule

```sh
uv run --extra adapters --extra surfaces pytest tests/conformance/authoring -q -k tier
uv run --extra adapters --extra surfaces pytest tests/conformance/intake -q -k isolation
```

Both must pass. The second is 037's, unchanged — run it here because a feature that extends an
isolation check is exactly where one gets accidentally relaxed.

Expected: a read-only subject mount is hardened, a **writable** one fails naming that clause,
and `repo_mounted=True` still fails with its original message.

## Scenario C — Nothing read leaves with what was written

```sh
uv run --extra adapters --extra surfaces pytest tests/conformance/authoring -q -k containment
```

Expected: C1–C5 pass. A seeded credential reaches neither the files, the commits, nor the
prose. An untouched file cannot appear in the proposal. A diff's surrounding context is
**present and not refused**.

**Prove it can fail.** Delete the seeded secret from the fixture subject and re-run: C1 must
**fail**, because a must-deny case that never puts a secret anywhere a generator could reach is
the passing stub ADR-0047 forbids and it is the most available one in this feature.

**Then read C4's companion row.** It records that a *paraphrase* of analysed content is **not**
caught. That is the residual risk, stated rather than discovered — the file half of containment
is structural, the prose half is inspected, and they are not the same strength.

## Scenario D — The agent is talked to, and does not listen

```sh
uv run --extra adapters --extra surfaces pytest tests/conformance/authoring -q -k redirection
```

Expected: R1–R2 pass. The artefact produced from a subject carrying instructions to the agent
is **byte-identical** to the artefact produced without them, and the attempt is recorded.

Byte-identical rather than "unaffected" is the point: "unaffected" is a judgement, and a row
requiring one is graded by whoever wrote it.

## Scenario E — It proposes, and it never enacts

```sh
uv run --extra adapters --extra surfaces pytest tests/conformance/authoring -q -k "proposal or provenance"
```

Expected: P1–P6 and V1–V3 pass. Nothing merges, nothing applies; a repository the requester
does not own is refused **before** anything is produced; a second proposal does not displace
the first.

**Worth reading: V2 beside V1.** V1 asserts the provenance rule fires; V2 asserts the ceilings
are disjoint so there is nothing for it to fire on. One is what survives a definition somebody
writes next year; the other is what is true today. Both, not one.

**And V3**, which asserts `terraform_apply` is unchanged. A feature that made the platform
safer by quietly narrowing an existing capability would have changed the product without
saying so.

## Scenario F — Correctness is two gates, and they disagree usefully

```sh
make eval-authoring     # CI gate lane — needs terraform + the pinned provider mirror
```

Expected: **two numbers, reported separately.** The case to look for is the one that
**validates cleanly and diverges from the reference** — a module wiring a static credential
where dynamic secrets were asked for. It passes gate one and fails gate two, which is the
whole reason there are two.

**If the tooling is unavailable this FAILS.** It does not skip, and it does not degrade to
`fmt`-only while still reporting "validated". Confirm that by running it with `terraform` off
the path: the lane must go red.

**Prove the floor bites.** Remove a must-deny class from `evals/authoring/` and re-run: the
corpus must **raise**, not warn. Then remove a golden task's human-authored reference: it must
be **refused** rather than scored on one gate. That second one is the clause most likely to
erode, and it erodes by generating the references — which measures the generator against
itself and passes everything.

## Scenario G — End to end, against a real host

```sh
make dev-up
# then dispatch an authoring run against a scratch repository you own
```

Expected: a proposal appears on the target repository containing the authored module and
nothing else; the trail carries `ARTIFACT_AUTHORED` and `PROPOSAL_OPENED`; **no merge event
exists** because the platform did not merge.

Then merge it by hand and confirm two things: the merge is **observed** rather than recorded as
a platform act, and applying the merged configuration afterwards is the ordinary governed
`terraform_apply` it always was.

**This is the scenario that proves the feature rather than its parts.** The assembly is the one
path no hermetic row covers — a dispatched run, a real tier with a real mount, a real
credential, a real host — and every previous feature that skipped it found something here.
