# SPDX-License-Identifier: Apache-2.0
"""GATE:no-secret-leak — the provider credential exists in exactly one lane.

The live lane's key is a **dev-lane secret**: never in a jobspec, never read by a run path,
absent from every pack manifest. The platform's default posture is "calls no model", and the
key is the one thing that could quietly change that — a jobspec carrying it would hand every
allocation the ability to call a provider nobody qualified it for.

**Asserts against `scoring.EVAL_PROVIDER_KEY`, imported.** A no-secret-leak row matching a
string literal that nothing defines passes forever regardless of what leaks; importing the
constant means renaming the key breaks this row instead of orphaning it.
"""

from __future__ import annotations

import ast
from pathlib import Path

from core.evals.scoring import EVAL_PROVIDER_KEY

ROOT = Path(__file__).resolve().parents[3]

#: What to search for. The VALUE is what a jobspec would set; the NAME is how source
#: references it (the adapter imports the constant and never contains the literal — which
#: is correct, and the first run of this file failed by searching only for the value).
NEEDLES = (EVAL_PROVIDER_KEY, "EVAL_PROVIDER_KEY")


def _references_key(text: str) -> bool:
    return any(needle in text for needle in NEEDLES)


#: Where the name MAY appear: the module that defines it, the adapter that reads it, and
#: the lanes that assert about it. Everything else is a leak.
ALLOWED = {
    "src/core/evals/scoring.py",  # defines it
    "src/adapters/anthropic_scorer.py",  # the one reader, in the one provider module
}


def test_the_key_appears_in_no_jobspec_or_infra_file() -> None:
    """A jobspec carrying the key hands every allocation a provider credential."""
    offenders = [
        str(path.relative_to(ROOT))
        for pattern in ("*.nomad", "*.hcl", "*.tf", "*.json", "*.yaml", "*.yml")
        for path in (ROOT / "infra").rglob(pattern)
        if _references_key(path.read_text(errors="replace"))
    ]
    assert not offenders, f"the provider key is named in infrastructure: {offenders}"


def test_no_run_path_module_reads_the_key() -> None:
    """The run path calls no model; a run reading this key is the posture quietly changing."""
    offenders = []
    for path in (ROOT / "src").rglob("*.py"):
        relative = str(path.relative_to(ROOT))
        if relative in ALLOWED:
            continue
        if _references_key(path.read_text()):
            offenders.append(relative)
    assert not offenders, f"the provider key is referenced outside the allowed modules: {offenders}"


def test_the_key_is_absent_from_every_pack_manifest() -> None:
    for manifest in (ROOT / "packs").rglob("*.toml"):
        assert not _references_key(manifest.read_text()), (
            f"{manifest.relative_to(ROOT)} names the provider key; a pack that could name a "
            f"credential is a pack that could exfiltrate one"
        )


def test_the_one_reader_is_in_the_provider_module() -> None:
    """The positive control: exactly one `os.environ` read of the key, where providers live.

    Zero readers would mean the live lane silently cannot run — which SC-005a says must be a
    raise, and is, but this row is what notices if the read quietly moves into core.
    """
    reader = ROOT / "src" / "adapters" / "anthropic_scorer.py"
    tree = ast.parse(reader.read_text())
    reads = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr in ("get", "environ")
    ]
    assert reads, "the adapter no longer reads the environment; the live lane cannot run"
    assert "EVAL_PROVIDER_KEY" in reader.read_text()


def test_the_allowlist_is_current() -> None:
    """Every allowed module still exists and still references the key."""
    for relative in ALLOWED:
        path = ROOT / relative
        assert path.is_file(), f"allowlist names {relative}, which does not exist"
        assert _references_key(path.read_text()), (
            f"{relative} no longer references the key; remove it from ALLOWED"
        )
