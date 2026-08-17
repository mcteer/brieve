# SPDX-License-Identifier: Apache-2.0
"""047 publishing shapes that 041's frozen A13 rows must not absorb.

Clone-then-materialize is the dispatched analyzer workspace (no ``.git``). Title on
``gh pr create`` is the composed summary, not an accident of argv order.
"""

from __future__ import annotations

from pathlib import Path

from tests.conformance.authoring.test_publishing import FakeForge, _publisher, _Source


def test_row_a13_a_workspace_without_git_clones_then_materializes(tmp_path: Path) -> None:
    """Dispatched shape: analyzer workspace has authored bytes, no ``.git`` (038 / 041).

    The proposer must not mount the subject, so it clones, applies the composed proposal, and
    pushes from that tree. Hermetic: the fake forge answers clone; the bytes on disk prove
    materialize used the proposal, not leftover workspace files.
    """
    forge, source = FakeForge(), _Source()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "leftover-from-analyzer.txt").write_text("not in the proposal\n")

    result = _publisher(forge, source, workspace)()

    assert "clone" in forge.flattened
    assert "--depth" in forge.flattened
    checkout = tmp_path / "publish-checkout"
    assert (checkout / "main.tf").read_text() == 'resource "x" {}\n'
    assert not (checkout / "leftover-from-analyzer.txt").exists(), (
        "materialize must apply the composed proposal, not copy the analyzer workspace"
    )
    assert result["number"] == 7


def test_row_a13_an_existing_checkout_does_not_clone_again(tmp_path: Path) -> None:
    """E1 shape: subject and workspace are the same acquired clone."""
    forge, source = FakeForge(), _Source()
    (tmp_path / ".git").mkdir()
    (tmp_path / "main.tf").write_text('resource "x" {}\n')

    _publisher(forge, source, tmp_path)()

    assert "clone" not in forge.flattened


def test_row_a13_the_create_title_is_the_proposal_title(tmp_path: Path) -> None:
    """``--title`` is the composed summary, not the first sentence of argv assembly."""
    forge, source = FakeForge(), _Source()
    _publisher(forge, source, tmp_path)()
    create = next(argv for argv, _ in forge.calls if "pr" in argv and "create" in argv)
    assert create[create.index("--title") + 1] == "Add a Vault integration"
