# SPDX-License-Identifier: Apache-2.0
"""CONFORMANCE — the platform obtains its authority to call a model, per task, or it refuses.

**This file exists because the answering capability was complete, gated, and unusable.** 024 built
it, 025 extended it, 026 governed it — and every ask through the served surface refused before
reaching a model, because putting a vendor credential inside a service was a constitutional
question nobody had answered. Three features recorded the deferral rather than resolving it.

**The three refusals are the design, and they are three different people's problems.** A cell the
matrix has not qualified sends someone to the matrix; a credential the store does not hold sends
them to whoever governs credentials; a vendor that will not answer sends them to the vendor. The
rows here assert that a reader of the trail can tell which, because collapsing any two of them
would send somebody to the wrong system during an incident.

**Counted at the provider and at the credential source, never read off the response.** A refusal
that returns the right status while having already called the vendor satisfies any response-level
check and violates the requirement. And a surface that fetched once and reused the key across asks
would satisfy every single-ask row while holding a credential for the life of the process — so the
credential source counts its reads too.
"""

from __future__ import annotations

import os
import pathlib
from typing import Any

import pytest
from fastapi.testclient import TestClient

from core.answering.answer import ProviderUnavailable
from core.answering.corpus import Corpus
from core.evals.scoring import EVAL_PROVIDER_KEY
from tests.harness.api_fixtures import (
    available_credential,
    qualified_ask_authority,
    surface_under_test,
)

GUIDANCE_QUESTION = "How does an AI agent obtain an identity with Vault?"
ESTATE_QUESTION = "Which runs were denied last night?"
MODEL = "anthropic/claude-opus@5"


class CountingProvider:
    """Answers plausibly, and remembers that it was asked.

    Plausibly on purpose: a failure to refuse then produces a *passing-looking* answer, which is
    the shape every gap in this area has taken.
    """

    def __init__(self) -> None:
        self.calls = 0
        self.secrets: list[str] = []

    def answer(self, question: str, material: Any) -> list[dict[str, Any]]:
        self.calls += 1
        if isinstance(material, Corpus):
            return [{"statement": "From the corpus.", "citations": []}]
        return [
            {
                "statement": "From the records.",
                "references": [{"entry_hash": r.entry_hash} for r in material[:1]],
            }
        ]


class RefusingProvider:
    """A vendor that will not answer — the third rung of the ladder."""

    def answer(self, question: str, material: Any) -> list[dict[str, Any]]:
        raise ProviderUnavailable("the vendor did not answer")


def _asks(surface: Any) -> list[Any]:
    return [e for e in surface.audit.all_entries() if str(e.event_type) == "ask_answered"]


def _qualified(**kwargs: Any) -> Any:
    """A surface whose governance PASSES, so what follows is about the credential alone."""
    kwargs.setdefault("ask_model", MODEL)
    kwargs.setdefault("ask_authority", qualified_ask_authority(model=MODEL))
    return surface_under_test(**kwargs)


# ------------------------------------------------------------------ T013: the headline


def test_a_qualified_cell_with_no_credential_refuses_and_calls_nothing() -> None:
    """SC-001's inverse, counted at the provider.

    Governance has passed — the matrix qualifies this cell and the binding names it — and the ask
    still refuses, because a qualified cell is not authority to call a vendor. Those are two
    different permissions held in two different places, and this row is what keeps them from
    collapsing into one.
    """
    provider = CountingProvider()
    surface = _qualified(ask_provider=provider, credential_source=None)

    response = TestClient(surface.app).post(
        "/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer()
    )

    assert response.status_code == 503
    assert provider.calls == 0, "the vendor was called without the platform holding authority to"
    record = _asks(surface)[0].payload
    assert record["disposition"] == "credential_unavailable"
    # Governance PASSED, and the record keeps saying so. Overwriting the resolution outcome with
    # the later failure would erase the fact that the cell was qualified — and an investigator
    # would then be unable to tell this from an unqualified ask.
    assert record["cell"] == f"vault:{MODEL}:ask"
    assert record["cell_disposition"] == "pinned"
    assert record["model_authority"] == ""


def test_a_credential_present_answers_and_the_record_carries_the_reference() -> None:
    provider = CountingProvider()
    surface = _qualified(ask_provider=provider, credential_source=available_credential())

    response = TestClient(surface.app).post(
        "/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer()
    )

    assert response.status_code == 200
    assert provider.calls == 1
    assert _asks(surface)[0].payload["model_authority"] == "vault:model-credentials/anthropic@v1"


def test_two_asks_are_two_fetches_and_no_surface_holds_a_key_between_them() -> None:
    """The property no single-ask row can see, and the whole posture in one assertion.

    A surface that fetched once at construction and reused the key would pass every other row in
    this file and hold a vendor credential for the life of the process — the standing credential
    Principle IV forbids, moved one layer up from the reader that refuses to cache.

    Asserted on **both surfaces**, because they build providers independently and a cache added to
    one would be invisible in the other's rows (ADR-0033).
    """
    credential = available_credential()
    surface = _qualified(ask_provider=CountingProvider(), credential_source=credential)
    client = TestClient(surface.app)

    client.post("/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer())
    client.post("/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer())
    surface.mcp.call("ask", {"question": GUIDANCE_QUESTION}, subject=surface.subject())

    assert len(credential.reads) == 3, (
        f"three asks produced {len(credential.reads)} credential reads; a surface is holding a "
        f"key across asks"
    )


# ------------------------------------------------------------------ T014: no env fallback


def test_the_production_path_never_falls_back_to_the_eval_lane_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GATE:fail-closed — the row three features' silence would have needed.

    **The environment variable is deliberately SET.** A production path that fell back to
    `EVAL_PROVIDER_API_KEY` would work on the operator's laptop, work in every hermetic row that
    happens to have it set, and fail only in the enclave where no such variable exists — the most
    expensive place to discover it. Every other row in this file passes whether or not the fallback
    exists; this one is the only thing standing between the platform and that fix.

    If this row is ever seen passing with the variable *unset*, it is testing nothing.
    """
    monkeypatch.setenv(EVAL_PROVIDER_KEY, "not-a-real-key-and-must-never-be-reached")
    assert os.environ.get(EVAL_PROVIDER_KEY), "this row is vacuous without the variable set"

    provider = CountingProvider()
    surface = _qualified(ask_provider=provider, credential_source=None)

    response = TestClient(surface.app).post(
        "/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer()
    )

    assert response.status_code == 503
    assert provider.calls == 0
    assert _asks(surface)[0].payload["disposition"] == "credential_unavailable"


# ------------------------------------------------------------------ T015: three refusals


def test_the_three_failures_stay_distinguishable_in_the_trail() -> None:
    """SC-006. Three failures, three people, and the trail says which without guessing.

    The order is the design: the cell is checked before the credential, and the credential before
    the vendor. Reversing any pair sends an operator to configure something they are not yet
    permitted to use, or to chase a vendor outage that is really a missing credential.
    """
    unqualified = surface_under_test(
        ask_provider=CountingProvider(),
        ask_model=MODEL,
        credential_source=available_credential(),
    )
    no_credential = _qualified(ask_provider=CountingProvider(), credential_source=None)
    vendor_down = _qualified(
        ask_provider=RefusingProvider(), credential_source=available_credential()
    )

    for surface in (unqualified, no_credential, vendor_down):
        TestClient(surface.app).post(
            "/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer()
        )

    assert _asks(unqualified)[0].payload["disposition"] == "unbound"
    assert _asks(no_credential)[0].payload["disposition"] == "credential_unavailable"
    # The vendor rung records nothing new of its own — `answer_question` raises and the surface
    # answers 503 — and that asymmetry is worth naming rather than papering over: the first two
    # are the platform's own decisions and the third is somebody else's outage.
    assert _asks(vendor_down) == []


def test_governance_is_checked_before_the_credential_is_sought() -> None:
    """The order, where it is observable: an unqualified ask never touches the store.

    A platform that fetched first would go looking for authority to make a call it was never
    permitted to make — and an operator watching credential reads would see traffic for asks that
    governance had already decided against.
    """
    credential = available_credential()
    surface = surface_under_test(
        ask_provider=CountingProvider(), ask_model=MODEL, credential_source=credential
    )

    TestClient(surface.app).post(
        "/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer()
    )

    assert credential.reads == [], "the store was read for an ask governance had already refused"


# ------------------------------------------------------------------ T016: never persisted


def test_the_key_appears_in_no_record_and_in_no_response_body() -> None:
    """GATE:no-secret-leak — FR-008, at both places a value could escape.

    The trail carries a **reference**: where the credential lives and which rotation generation was
    in force. Not the key, and not a hash of it — a hash of a low-entropy-format secret is an
    oracle, and the platform's rule everywhere else is references only.

    The asker is present beside it (SC-004a): the platform calls the vendor as itself, and *for
    whom* has to remain answerable or an audit of model use answers nothing about people.
    """
    secret = "brokered-and-must-never-be-written-anywhere"
    credential = available_credential(secret=secret)
    surface = _qualified(ask_provider=CountingProvider(), credential_source=credential)

    response = TestClient(surface.app).post(
        "/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer()
    )

    assert secret not in response.text
    for entry in surface.audit.all_entries():
        assert secret not in str(entry.payload), f"the key reached {entry.event_type}'s payload"

    record = _asks(surface)[0].payload
    assert record["model_authority"].startswith("vault:model-credentials/")
    assert secret not in record["model_authority"]
    assert record["subject_user_id"] == "alice"


# ------------------------------------------------------------------ T017: one reader


def test_both_paths_reach_one_credential_reader_and_no_other() -> None:
    """SC-002 / FR-003, scoped to what a hermetic row can honestly check.

    **The providers differ by path and always have** — `LiveAnswerProvider` on the answering path,
    `ModelChooser` on the run path — and unifying those is not the design. What must be one is the
    **credential mechanism**: two ways to obtain authority to call a vendor is the fragmentation
    Principle VII forbids, and it is the failure mode where one path gets a fix and the other does
    not.

    Asserted by parsing rather than by running, because the run path only executes under an
    attested workload identity (`@pytest.mark.enclave`) and a single hermetic row cannot exercise
    both halves. The *behavioural* run-path half is owed in the enclave lane; this row is the
    structural claim, and it is the one that fails when somebody adds a second reader.
    """
    import ast
    import pathlib

    src = pathlib.Path(__file__).resolve().parents[3] / "src"
    assembly = [
        src / "surfaces" / "mcp" / "served.py",
        src / "surfaces" / "dispatch" / "entrypoint.py",
    ]

    #: Anything that would constitute a second way to obtain a vendor credential.
    RIVALS = ("EVAL_PROVIDER_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY")

    for path in assembly:
        source = path.read_text(encoding="utf-8")
        names = {node.id for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Name)} | {
            alias.asname or alias.name
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        assert "BrokeredModelCredential" in names, (
            f"{path.name} does not reach the one credential reader; if this path no longer needs "
            f"a model credential, remove it from this row and say why"
        )
        for rival in RIVALS:
            assert rival not in source, f"{path.name} names a second credential source: {rival}"


# ------------------------------------------------------------------ T018/T019: revocation


def test_deleting_the_credential_refuses_the_next_ask_with_no_restart() -> None:
    """SC-003 — revocation is a store operation, and it binds immediately.

    The same surface object, the same process, no reconstruction of anything: one ask answers, the
    record is emptied, and the next ask refuses. That is what "no restart" means, and it is only
    true because the reader refuses to cache — a surface that had kept the key would keep answering
    after revocation and nothing would show it.

    **The moment is locatable**: the last answered record and the first refused one are adjacent on
    the ask stream, so an investigator can say when the platform stopped being able to call the
    vendor without correlating against a deployment log.
    """
    credential = available_credential()
    surface = _qualified(ask_provider=CountingProvider(), credential_source=credential)
    client = TestClient(surface.app)

    answered = client.post("/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer())
    assert answered.status_code == 200

    credential.revoke()

    refused = client.post("/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer())
    assert refused.status_code == 503

    records = [a.payload for a in _asks(surface)]
    # The first ask REACHED the model — whether the model's claims survived citation resolution is
    # a different question and not this row's. What matters is that authority was exercised, which
    # is exactly what a carried reference means.
    assert records[-2]["disposition"] != "credential_unavailable"
    assert records[-2]["model_authority"] == "vault:model-credentials/anthropic@v1"
    assert records[-1]["disposition"] == "credential_unavailable"
    assert records[-1]["model_authority"] == ""


def test_rotation_moves_the_recorded_generation_without_interrupting_anything() -> None:
    """The half of revocation that must NOT refuse: a rotation is not an outage.

    The reference's version is what makes "before the leak or after the rotation" answerable from
    the record. If rotation did not move it, the field would name a location and nothing else — and
    a plain path is a fact nobody needs, since it is the same for every ask forever.
    """
    credential = available_credential()
    surface = _qualified(ask_provider=CountingProvider(), credential_source=credential)
    client = TestClient(surface.app)

    client.post("/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer())
    credential.rotate("the-new-generation")
    assert (
        client.post(
            "/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer()
        ).status_code
        == 200
    )

    generations = [a.payload["model_authority"] for a in _asks(surface)]
    assert generations == [
        "vault:model-credentials/anthropic@v1",
        "vault:model-credentials/anthropic@v2",
    ]


def test_an_ask_that_already_holds_a_credential_completes_after_it_is_revoked() -> None:
    """The row that guards against satisfying revocation too literally.

    Revocation binds the **next** task, exactly like every per-task grant this platform
    manufactures. A fix that reached back into a task already in flight — re-checking the store
    mid-answer, or invalidating a held credential — would be a different and worse guarantee: it
    would make an ask's outcome depend on when an unrelated operator ran a command.

    Emptying the store *after* the fetch and observing the ask still complete is the assertion.
    The one after it refuses, which the row above proves.
    """
    credential = available_credential()

    class RevokesMidAnswer:
        """Empties the store at the moment the model would be called."""

        def __init__(self) -> None:
            self.calls = 0

        def answer(self, question: str, material: Any) -> list[dict[str, Any]]:
            self.calls += 1
            credential.revoke()
            return [{"statement": "From the corpus.", "citations": []}]

    provider = RevokesMidAnswer()
    surface = _qualified(ask_provider=provider, credential_source=credential)

    response = TestClient(surface.app).post(
        "/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer()
    )

    assert response.status_code == 200, "revocation reached back into a task already in flight"
    assert provider.calls == 1
    record = _asks(surface)[-1].payload
    assert record["disposition"] != "credential_unavailable"
    # And it recorded the authority it ACTUALLY held, not the store's state at the end.
    assert record["model_authority"] == "vault:model-credentials/anthropic@v1"


# ------------------------------------------------------------------ T016a: the run half


def test_a_fixture_model_never_reaches_the_credential_store() -> None:
    """FR-011 at the branch that decides it, and the half most worth pinning.

    Every blocking lane in this repository runs on `fixture:` cells, and they must keep running
    with no model credential anywhere — which is the state a fresh enclave is in. A run path that
    fetched unconditionally would break all of them the moment the store was empty, and a reader
    that ran first and discarded its result for fixtures would satisfy any behavioural check while
    doing exactly that.

    Asserted against the branch rather than through a dispatch because `_run_task` needs an
    attested workload identity, so a hermetic row cannot exercise it. The *behaviour* is owed in
    the enclave lane; this is the structure, and it is what fails when somebody moves the fetch.
    """
    import inspect

    from surfaces.dispatch import entrypoint

    source = inspect.getsource(entrypoint._chooser_for)  # noqa: SLF001 — the branch IS the claim
    assert source.index("FIXTURE_PROVIDER") < source.index("BrokeredModelCredential"), (
        "the credential is fetched before the fixture branch is taken; a fixture run would then "
        "require a vendor credential to exist, and every blocking lane runs on fixture cells"
    )


def test_the_run_path_fetches_after_the_cell_is_validated_and_before_anything_is_built() -> None:
    """The same order as the ask path, for the same reason — and that sameness is the point.

    `resolve_bound_model` validates the cell against the matrix; only then is the credential
    sought; only then is a chooser constructed. Fetching first would send an operator looking for
    authority to make a call the matrix had already refused.

    Two paths with the same order is what "both paths, one reader" has to mean beyond sharing a
    class: a reader shared by two call sites that check in different orders gives two different
    answers to *which failure is this*.
    """
    import inspect

    from surfaces.dispatch import entrypoint

    source = inspect.getsource(entrypoint._chooser_for)  # noqa: SLF001
    # Matched on the CALL, not on its first argument's formatting. The earlier form looked
    # for "build_chooser(model" and broke the moment that call gained enough arguments to
    # wrap — which says nothing about the ordering this row exists to assert. That is the
    # seventh time a check in this repository has matched how code is written rather than
    # what it does, and the property here is the sequence, not the line breaks.
    assert (
        source.index("resolve_bound_model")
        < source.index("BrokeredModelCredential")
        < source.index("build_chooser(")
    )


# ------------------------------------------------------------------ parity and deployability


def test_both_surfaces_refuse_the_missing_credential_identically() -> None:
    """ADR-0033. One shared function, so the two surfaces cannot refuse differently.

    Parity is asserted here rather than left to inspection because the credential step is new on
    both paths at once, and a step added to one surface and *almost* added to the other is the
    divergence surface parity exists to catch. Both must give the same status and record the same
    disposition — a caller must not learn which transport they used from how they were refused.
    """
    surface = _qualified(ask_provider=CountingProvider(), credential_source=None)

    api = TestClient(surface.app).post(
        "/ask", json={"question": GUIDANCE_QUESTION}, headers=surface.bearer()
    )
    mcp = surface.mcp.call("ask", {"question": GUIDANCE_QUESTION}, subject=surface.subject())

    assert api.status_code == mcp.status == 503
    dispositions = {a.payload["disposition"] for a in _asks(surface)}
    assert dispositions == {"credential_unavailable"}
    assert len(_asks(surface)) == 2, "one surface refused without recording that someone asked"


def test_the_vendor_sdk_ships_with_the_extra_the_surface_jobspecs_install() -> None:
    """The defect a green test suite cannot see, pinned so it cannot come back.

    Until 027 no production path called a vendor, so the SDK was genuinely eval-only. The moment a
    served surface brokered a credential and built a provider, that stopped being true — and the
    surface jobspecs install `--extra adapters --extra surfaces`, never `--extra evals`. Left as
    it was, the first deployed ask would have fetched its credential, resolved its cell, and then
    failed at `import anthropic` with a message telling the operator to install an **eval** extra:
    a live-lane error, reported to somebody running the product, at the last step, after
    everything else had worked.

    Invisible to every row in this repository, because the developer venv has all extras. Only the
    allocation would have found it. So the check is against the declared dependency set rather
    than against what happens to be importable here.
    """
    import tomllib

    root = pathlib.Path(__file__).resolve().parents[3]
    extras = tomllib.loads((root / "pyproject.toml").read_text())["project"][
        "optional-dependencies"
    ]
    assert any(dep.startswith("anthropic") for dep in extras["adapters"]), (
        "the vendor SDK is not in the `adapters` extra. A served surface calls a vendor as of "
        "027, and the surface jobspecs install `adapters` and `surfaces` — never `evals`"
    )

    installed = [
        spec.read_text(encoding="utf-8")
        for spec in sorted((root / "infra/jobs").glob("*.nomad.hcl"))
        if "surfaces.mcp.served" in spec.read_text(encoding="utf-8")
    ]
    assert installed, "no jobspec runs the served surface; this row is checking nothing"
    for spec in installed:
        assert "--extra adapters" in spec, (
            "the served-surface jobspec does not install the extra carrying the vendor SDK and "
            "the provider adapter; the surface would fail at the vendor call"
        )


def test_both_deployed_assemblies_wire_the_same_ask_collaborators() -> None:
    """ADR-0033 where it actually binds: the assemblies, which no other row constructs.

    **This is the row the fourth analysis pass was doing by hand.** 026 wired `ask_authority` into
    `served.py` and not into `service.py`; 027 was about to wire the credential the same way. Both
    features' parity rows were green the whole time, and they were right to be — they compare two
    surfaces built from ONE set of collaborators in a fixture, which is the correct thing to check
    about the shared operation and says nothing about what a deployment stands up.

    So the divergence had a place to hide for two features: the surfaces agree, the assemblies do
    not, and the difference is only visible to somebody reading both files side by side. This row
    reads them.

    It checks that each collaborator is *named* in both, not that they resolve to the same object —
    a deployment legitimately builds its own. What must not differ is whether a transport has one
    at all, because that is the difference between a person getting an answer and a person getting
    a 503 that depends on which client they picked.
    """
    root = pathlib.Path(__file__).resolve().parents[3] / "src" / "surfaces"
    assemblies = {
        "api/service.py": (root / "api" / "service.py").read_text(encoding="utf-8"),
        "mcp/served.py": (root / "mcp" / "served.py").read_text(encoding="utf-8"),
    }

    for collaborator in ("ask_authority", "ask_providers", "credential_source", "ASK_MODEL"):
        missing = [name for name, text in assemblies.items() if collaborator not in text]
        assert not missing, (
            f"{collaborator!r} is wired in one deployed assembly and not in {missing}. A person "
            f"asking the same question through two transports would get different answers, and "
            f"the parity rows cannot see it — they build both surfaces from one set of "
            f"collaborators"
        )


def test_a_checkpoint_cannot_carry_the_credential_and_a_resume_refetches() -> None:
    """The checkpoint half of *never persisted*, and FR-010 in its reconciled form.

    **Two claims, and the second is why the first is not enough.** `CheckpointBlob` declares its
    fields with `extra="forbid"`, so nothing can be smuggled onto it — but `payload` is an opaque
    dict, and a chooser holding a key would reach it the moment somebody serialised run state
    wholesale. What actually keeps the key out is that the chooser is built **per allocation** and
    is not part of what a checkpoint holds.

    **A resume re-authenticates rather than replaying.** Both the fresh path and the revive path
    go through `_chooser_for`, so a resumed run fetches the credential again under its new
    allocation's own attested identity. That is what makes FR-010 true in a posture where nothing
    expires: a revived run cannot continue on authority obtained by a process that is gone, and if
    the credential was withdrawn in between, the revival refuses.
    """
    import inspect

    from core.durability.types import CheckpointBlob
    from surfaces.dispatch import entrypoint

    declared = set(CheckpointBlob.model_fields)
    assert not {f for f in declared if "cred" in f or "secret" in f or "key" in f}
    assert CheckpointBlob.model_config.get("extra") == "forbid"

    source = inspect.getsource(entrypoint)
    assert source.count("_chooser_for(") >= 3, (
        "one of the run paths no longer builds its chooser through `_chooser_for`; a path that "
        "constructed one directly would skip the credential fetch, or reuse one across allocations"
    )


def test_both_surface_jobspecs_ship_the_corpus_a_guidance_ask_reads() -> None:
    """The last link, and the fifth defect of the same class this feature found.

    A deployed guidance ask loads the pinned corpus. Neither surface jobspec copied it into the
    allocation — they copy `src` and nothing else — so **every guidance ask through a deployed
    surface answered 503 naming `corpus-sync`**, no matter how correct the credential, the cell,
    and the binding were. Found by asking the running surface a question, which is the only thing
    that could have found it: the corpus loads from the repository root in every test process.

    Optional on purpose. An enclave whose operator has not synced a corpus still starts, and the
    ask says which command to run. Copying unconditionally under `set -e` would turn a legible
    503 into a surface that will not start, which is a worse answer to the same situation.
    """
    root = pathlib.Path(__file__).resolve().parents[3]
    served = [
        (spec.name, spec.read_text(encoding="utf-8"))
        for spec in sorted((root / "infra/jobs").glob("*.nomad.hcl"))
        if "surfaces.mcp.served" in spec.read_text(encoding="utf-8")
        or "surfaces.api.service" in spec.read_text(encoding="utf-8")
    ]
    assert len(served) == 2, f"expected both answering surfaces, found {[n for n, _ in served]}"

    for name, text in served:
        assert "/src/corpus" in text, (
            f"{name} does not copy the corpus into the allocation; every guidance ask through "
            f"this surface will answer 503 regardless of credential, cell or binding"
        )
        assert "|| true" in text, (
            f"{name} copies the corpus without tolerating its absence; an enclave with no synced "
            f"corpus would fail to START rather than answering a 503 that names the fix"
        )
