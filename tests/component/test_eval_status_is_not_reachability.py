# SPDX-License-Identifier: Apache-2.0
"""A pack's eval status and its tool reachability are separate facts (edge case 2).

**Green gates over a capability that cannot run.** The Terraform pack's suites pass and its
tools are fixture-backed by decision, because Terraform is not deployed in the enclave. The
Vault pack's tools reach a product that actually answers.

Both packs will show four green suites. If anything derived "this pack works end to end"
from that, the record would claim something about Terraform that nobody has demonstrated —
and the tool half is exactly what Principle II governs, so it is the half that must not be
inferred.

Keeping the two facts distinguishable is the whole answer to that edge case. There is no
mechanism here to get right; there is a conflation to refuse to build.
"""

from __future__ import annotations

from pathlib import Path

from core.packs.loader import FilesystemPackLoader
from core.packs.manifest import PackManifest

PACKS_ROOT = Path(__file__).resolve().parents[2] / "packs"


def _manifest(name: str) -> PackManifest:
    return FilesystemPackLoader(PACKS_ROOT).load(name)


def test_a_manifest_carries_no_field_asserting_its_tools_work() -> None:
    """The conflation is refused by absence.

    A `verified` or `end_to_end` flag on the manifest would be a pack declaring its own
    tools functional — a claim from the least qualified source, and one that eval results
    would eventually be read as backing.
    """
    fields = set(PackManifest.__dataclass_fields__)
    for suspicious in ("verified", "end_to_end", "tools_proven", "reachable"):
        assert suspicious not in fields, (
            f"PackManifest declares {suspicious!r}; a pack must not assert that its own "
            f"tools work, and eval results must not be read as evidence that they do"
        )


def test_eval_coverage_says_nothing_about_reachability() -> None:
    """Both packs declare the same suites at the same floor.

    So the eval record cannot distinguish them — which is correct, and is exactly why it
    must not be the thing anyone reads to learn whether a pack's tools were called.
    """
    terraform = _manifest("terraform")
    vault = _manifest("vault")
    assert set(terraform.eval_suites) == set(vault.eval_suites)
    assert terraform.eval_case_counts == vault.eval_case_counts


def test_the_record_states_which_pack_is_fixture_backed() -> None:
    """FR-027c: a pack whose tools were never called must not read as one whose tools were.

    Asserted against the record rather than against the code, because this is a claim about
    what someone reading the repository is told. The manifest is where a reader looks first.
    """
    terraform_manifest = (PACKS_ROOT / "terraform" / "pack.toml").read_text()
    assert "fixture-backed" in terraform_manifest, (
        "the Terraform pack does not state that its tool layer is fixture-backed; its "
        "suites go green either way, and a reader would take that as end-to-end proof"
    )


def test_the_vault_pack_is_the_one_whose_tools_reach_a_live_product() -> None:
    """The other half of the same distinction, stated positively.

    Without this, "fixture-backed" reads as a limitation of the pack system rather than as
    a fact about one pack's product not being deployed here.
    """
    vault_manifest = (PACKS_ROOT / "vault" / "pack.toml").read_text()
    assert "runs in the enclave" in vault_manifest or "actually answers" in vault_manifest
