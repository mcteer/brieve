# SPDX-License-Identifier: Apache-2.0
"""A13-A17 — publishing, idempotently, without leaving a credential anywhere (041, US3).

The forge is a declared fake: a `CommandRunner` that records every argv and answers the two
queries `gh` would. **Declared rather than incidental** — this repository refuses undeclared
fakes, and a row about publishing that quietly stubbed the publish would assert nothing.

What the fake cannot prove is that `gh` behaves as expected; that is E1's job, in the enclave,
against a real repository. What it proves here is the shape: one proposal per key, an
interrupted publish resolved by looking rather than guessing, and a token that appears in no
argv, no file, and no record.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from core.authoring.credential import InstallationToken
from core.authoring.proposal import Proposal, ProposalState, ProposedFile, branch_for
from core.authoring.publish import (
    ProposalObserver,
    ProposalPublisher,
    PublishRefused,
    _Completed,
)
from core.observation.types import ObservationOutcome

DECLARED_FAKE_FORGE = (
    "A CommandRunner standing in for `git` and `gh`. It answers the two queries the publish "
    "path makes and records every argv, so rows can assert the shape of publishing and the "
    "absence of a credential. E1 runs the real thing in the enclave."
)

REPO = "acme/infra"
KEY = "run-041-abc"
TOKEN = "ghs_a_real_looking_token_value"


class _Source:
    """Mints the installation token, and counts how often it was asked."""

    def __init__(self, token: str = TOKEN) -> None:
        self.token = token
        self.calls = 0

    def token_for(self, installation: str) -> InstallationToken:
        self.calls += 1
        return InstallationToken(
            token=self.token,
            installation=installation,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )


@dataclass
class FakeForge:
    """Records argv and env for every call, and answers `gh pr list`."""

    open_numbers: list[int] = field(default_factory=list)
    fail: str | None = None
    calls: list[tuple[list[str], dict[str, str]]] = field(default_factory=list)

    def __call__(
        self, argv: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None
    ) -> _Completed:
        self.calls.append((list(argv), dict(env or {})))
        joined = " ".join(argv)
        if self.fail and self.fail in joined:
            return _Completed(returncode=1, stdout="", stderr="refused")
        if "pr list" in joined:
            payload = [
                {"number": n, "url": f"https://github.com/{REPO}/pull/{n}"}
                for n in self.open_numbers
            ]
            return _Completed(returncode=0, stdout=json.dumps(payload))
        if "pr create" in joined:
            self.open_numbers.append(7)
            return _Completed(returncode=0, stdout=f"https://github.com/{REPO}/pull/7\n")
        return _Completed(returncode=0, stdout="")

    @property
    def flattened(self) -> str:
        return " ".join(" ".join(argv) for argv, _env in self.calls)


def _proposal(*, files: bool = True, rationale: str = "Wires dynamic secrets.") -> Proposal:
    return Proposal(
        target_repository=REPO,
        branch=branch_for(KEY),
        task="Add a Vault integration",
        files=(
            [ProposedFile(path="main.tf", body='resource "x" {}\n', is_diff=False)] if files else []
        ),
        rationale=rationale,
    )


def _publisher(
    forge: FakeForge, source: _Source, tmp_path: Path, **kw: object
) -> ProposalPublisher:
    return ProposalPublisher(
        proposal=kw.pop("proposal", None) or _proposal(),  # type: ignore[arg-type]
        workspace=tmp_path,
        token_source=source,
        installation="inst-1",
        runner=forge,
        **kw,  # type: ignore[arg-type]
    )


def test_row_a13_one_key_yields_one_proposal(tmp_path: Path) -> None:
    """A13 — the deterministic branch is the idempotency mechanism (FR-025, SC-010)."""
    forge, source = FakeForge(), _Source()

    first = _publisher(forge, source, tmp_path)()
    assert first["reused"] is False
    assert first["number"] == 7

    second = _publisher(forge, source, tmp_path)()
    assert second["reused"] is True, "a second publish must find the first, never open another"
    assert second["number"] == 7
    assert forge.flattened.count("pr create") == 1


def test_row_a13_the_push_is_force_with_lease_never_force(tmp_path: Path) -> None:
    """A human's edits to the branch must make the push refuse, not vanish."""
    forge, source = FakeForge(), _Source()
    _publisher(forge, source, tmp_path)()

    push = next(argv for argv, _ in forge.calls if "push" in argv)
    assert "--force-with-lease" in push
    assert "--force" not in push


def test_row_a14_the_observer_finds_an_existing_proposal(tmp_path: Path) -> None:
    """A14 — an interrupted publish is resolved by looking (FR-010)."""
    forge, source = FakeForge(open_numbers=[7]), _Source()
    observer = ProposalObserver(
        repository=REPO, token_source=source, installation="inst-1", runner=forge
    )

    observation = observer.observe(idempotency_key=KEY)

    assert observation.outcome is ObservationOutcome.HAPPENED
    assert branch_for(KEY) in forge.flattened


def test_row_a14_the_observer_reports_absence_distinctly(tmp_path: Path) -> None:
    forge, source = FakeForge(open_numbers=[]), _Source()
    observer = ProposalObserver(
        repository=REPO, token_source=source, installation="inst-1", runner=forge
    )

    assert observer.observe(idempotency_key=KEY).outcome is ObservationOutcome.DID_NOT_HAPPEN


def test_row_a14_an_unreachable_forge_cannot_determine(tmp_path: Path) -> None:
    """The one answer that must never be guessed."""
    forge, source = FakeForge(fail="pr list"), _Source()
    observer = ProposalObserver(
        repository=REPO, token_source=source, installation="inst-1", runner=forge
    )

    assert observer.observe(idempotency_key=KEY).outcome is ObservationOutcome.CANNOT_DETERMINE


def test_row_a14_the_observer_and_the_handler_ask_the_same_question(tmp_path: Path) -> None:
    """One implementation, so the two cannot disagree about what "already open" means."""
    handler_forge, source = FakeForge(open_numbers=[7]), _Source()
    _publisher(handler_forge, source, tmp_path)()

    observer_forge = FakeForge(open_numbers=[7])
    ProposalObserver(
        repository=REPO, token_source=source, installation="inst-1", runner=observer_forge
    ).observe(idempotency_key=KEY)

    def _list_call(forge: FakeForge) -> list[str]:
        return next(argv for argv, _ in forge.calls if "list" in argv)

    handler_query = [a for a in _list_call(handler_forge) if a not in ("number,url", "number")]
    observer_query = [a for a in _list_call(observer_forge) if a not in ("number,url", "number")]
    assert handler_query == observer_query


def test_row_a15_the_token_appears_in_no_argv(tmp_path: Path) -> None:
    """A15 — not in a remote URL, not on a command line (FR-023a)."""
    forge, source = FakeForge(), _Source()
    _publisher(forge, source, tmp_path)()

    assert TOKEN not in forge.flattened


def test_row_a15_the_token_travels_only_in_a_per_call_environment(tmp_path: Path) -> None:
    """Present where it must be, absent everywhere else — including the parent's environment."""
    import os

    forge, source = FakeForge(), _Source()
    _publisher(forge, source, tmp_path)()

    envs = [env for _argv, env in forge.calls]
    assert all(env.get("GH_TOKEN") == TOKEN for env in envs), "gh reads GH_TOKEN"
    assert "GH_TOKEN" not in os.environ, (
        "the token must never be placed in the parent process environment, where it would "
        "outlive the call and reach every later subprocess"
    )


def test_row_a15_git_reaches_the_token_through_the_helper_and_clears_the_system_one(
    tmp_path: Path,
) -> None:
    """One delivery path, and no chance of a developer's global helper authenticating a push."""
    forge, source = FakeForge(), _Source()
    _publisher(forge, source, tmp_path)()

    push = next(argv for argv, _ in forge.calls if "push" in argv)
    assert "credential.helper=" in push, "the system helper must be cleared"
    assert "credential.helper=!gh auth git-credential" in push


def test_row_a15_nothing_is_written_to_disk_by_publishing(tmp_path: Path) -> None:
    """No `hosts.yml`, no credential store, no config left behind."""
    forge, source = FakeForge(), _Source()
    _publisher(forge, source, tmp_path)()

    assert list(tmp_path.iterdir()) == [], (
        "the publish path must leave nothing on disk; `gh auth login` would write hosts.yml"
    )


def test_row_a15_the_returned_payload_carries_no_body(tmp_path: Path) -> None:
    """A proposal is a derivative of a private repository; the record gets a reference."""
    forge, source = FakeForge(), _Source()
    result = _publisher(forge, source, tmp_path)()

    assert set(result) == {"repository", "branch", "number", "url", "reused"}
    assert "Wires dynamic secrets" not in json.dumps(result)


def test_row_a16_an_empty_artefact_is_refused_before_publishing(tmp_path: Path) -> None:
    """A16 — a proposal with no files asks a person to review nothing."""
    forge, source = FakeForge(), _Source()
    publisher = _publisher(forge, source, tmp_path, proposal=_proposal(files=False))

    with pytest.raises(PublishRefused) as exc:
        publisher()

    assert exc.value.reason_code == "empty_proposal"
    assert forge.calls == [], "nothing may reach the forge once the artefact is known empty"


def test_row_a16_a_containment_refused_proposal_never_publishes(tmp_path: Path) -> None:
    """The refusal must bind at the publish seam, not only where containment ran."""
    proposal = _proposal()
    proposal.state = ProposalState.REFUSED
    forge, source = FakeForge(), _Source()

    with pytest.raises(PublishRefused) as exc:
        _publisher(forge, source, tmp_path, proposal=proposal)()

    assert exc.value.reason_code == "containment_refused"
    assert forge.calls == []


def test_the_rationale_reaches_the_scanned_body(tmp_path: Path) -> None:
    """FR-032 — the description is content, and 038's `scannable_text` already covers it.

    Asserted here because the requirement is easy to satisfy by accident and easy to break by
    composing the body somewhere else: the published body must be the SAME rendering the
    containment scan reads.
    """
    from core.authoring.proposal import scannable_text

    proposal = _proposal(rationale="A planted marker phrase")
    scanned = dict(scannable_text(proposal))
    assert "A planted marker phrase" in scanned["body"]

    forge, source = FakeForge(), _Source()
    _publisher(forge, source, tmp_path, proposal=proposal)()

    create = next(argv for argv, _ in forge.calls if "create" in argv)
    body = create[create.index("--body") + 1]
    assert body == proposal.render(), (
        "the published body must be the rendering containment scanned; composing it separately "
        "would leave the published text unscanned"
    )


def test_an_unconfirmable_publish_refuses_rather_than_claiming_success(tmp_path: Path) -> None:
    """An exit status is not evidence a proposal exists."""

    class _Silent(FakeForge):
        def __call__(self, argv, *, cwd=None, env=None):  # type: ignore[no-untyped-def]
            result = super().__call__(argv, cwd=cwd, env=env)
            if "pr create" in " ".join(argv):
                self.open_numbers.clear()  # the forge said yes and lists nothing
            return result

    forge, source = _Silent(), _Source()

    with pytest.raises(PublishRefused) as exc:
        _publisher(forge, source, tmp_path)()

    assert exc.value.reason_code == "proposal_unconfirmed"


def test_a_failed_list_refuses_rather_than_risking_a_duplicate(tmp_path: Path) -> None:
    """If we cannot tell whether one is open, opening another is the wrong guess."""
    forge, source = FakeForge(fail="pr list"), _Source()

    with pytest.raises(PublishRefused) as exc:
        _publisher(forge, source, tmp_path)()

    assert exc.value.reason_code == "forge_unreachable"


def test_row_a17_a_publishing_suspension_carries_a_product(tmp_path: Path) -> None:
    """A17 — the sweeper watches products, so a suspension must name one (FR-029/030).

    Until 041 `open_proposal` mapped to nothing: `dependency_products` was built from pack
    manifests and this is a platform tool. A run suspended on it carried a tool name that no
    product recovery could ever match, and `toolset.py` already states the consequence — it
    would have waited forever.
    """
    from surfaces.toolset import PLATFORM_TOOL_PRODUCTS, build_registry, dependency_products

    _registry, loaded = build_registry(packs=["vault"])
    mapped = dependency_products(loaded)

    assert mapped["open_proposal"] == "github"
    assert PLATFORM_TOOL_PRODUCTS["open_proposal"] == "github"


def test_row_a17_the_product_is_probed_by_the_table_the_checker_reads(tmp_path: Path) -> None:
    """The half that was actually missing: a probe in a dict nothing consults never fires."""
    from surfaces.probes import probes_for
    from surfaces.toolset import build_registry

    _registry, loaded = build_registry(packs=["vault"])
    table = probes_for(loaded)

    assert "github" in table, (
        "the health checker's product->probe table must carry `github`, or the dependency "
        "gate denies open_proposal while the forge is up"
    )
    assert callable(table["github"])
