# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — the core does not know what any managed product is (SC-002, FR-004).

**The distinction a pattern-only check gets wrong.** `src/core` mentions Vault and Nomad,
and must: `VaultDatabaseCredentials` is where a run's own credential comes from, and
`NomadWorkloadIdentity` is the attested identity it comes with. That is the core knowing its
**substrate**, not knowing a product it operates. A grep for "vault" either forbids the
trust fabric or, tuned to allow it, stops noticing when a pack's product leaks in.

So two things are separated here:

**Prose versus code.** Docstrings and comments discussing Terraform are the core being
*explained*, not the core *knowing*. Comments never reach the AST at all; docstrings are
stripped deliberately. What is checked is identifiers, attributes, imports, and string
constants — the places where naming a product would change behaviour.

**Substrate versus managed product.** `vault` and `nomad` are allowed, in named modules,
because the platform runs on them. `terraform`, `packer`, and `consul` are allowed nowhere,
because the platform *operates* them — through packs, whose whole claim is that the core
stays blind to them.

Vault is deliberately both, and that is the sharpest version of the rule: the core knows
Vault-the-trust-fabric and must never know Vault-the-managed-product. `vault_read` is a tool
in `packs/vault/pack.toml`; nothing under `src/core` has heard of it.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "src" / "core"

#: Products this platform OPERATES. Permitted nowhere in core code, with no exclusions —
#: every one of these arrives through a pack or it does not arrive.
MANAGED_PRODUCTS = ("terraform", "packer", "consul")

#: Products this platform RUNS ON. The core reaches these to obtain its own credentials and
#: its own attested identity, which is a different relationship entirely.
SUBSTRATE = ("vault", "nomad")

#: Where substrate names are permitted, by name and with the reason — the `ENCLAVE_PATHS`
#: pattern, so adding a third is a decision somebody makes on the record.
SUBSTRATE_ALLOWED = {
    # The trust fabric itself: ceilings, role bindings, the matrix, definition bindings.
    "authority/vault_fabric.py": "reads the control-plane trust fabric",
    # Where a run's database credential comes from, and the identity it comes with.
    "durability/credentials.py": "manufactures the run's own credentials",
    "durability/__init__.py": "package docstring naming the credential path",
    "durability/postgres.py": "obtains its connection credential from the fabric",
    "audit/postgres_sink.py": "obtains its connection credential from the fabric",
    "audit/postgres_query.py": "obtains its connection credential from the fabric",
    "dependencies/store.py": "obtains its connection credential from the fabric",
    "runs/changes.py": "reads gated change status from the fabric",
}


def _strip_docstrings(tree: ast.AST) -> ast.AST:
    """Prose about a product is not the core knowing one."""
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            node.body = body[1:]
    return tree


def _named_in_code(path: Path, products: tuple[str, ...]) -> set[str]:
    """Products appearing where they would change behaviour, not where they are discussed."""
    tree = _strip_docstrings(ast.parse(path.read_text(), filename=str(path)))
    found: set[str] = set()
    for node in ast.walk(tree):
        match node:
            case ast.Name():
                text = node.id
            case ast.Attribute():
                text = node.attr
            case ast.arg():
                text = node.arg
            case ast.Constant(value=str() as value):
                text = value
            case ast.FunctionDef() | ast.AsyncFunctionDef() | ast.ClassDef():
                text = node.name
            case ast.alias():
                text = f"{node.name} {node.asname or ''}"
            case ast.ImportFrom():
                text = node.module or ""
            case _:
                continue
        # Word-boundary tokens, not substrings: `consul` is a substring of `consulted`,
        # and the first run of this row flagged provenance-at-READ for naming a product it
        # has never heard of. Case transitions split too, or `VaultIdentityFabric`
        # tokenizes as one word and the trust fabric vanishes from its own allowlist —
        # which the allowlist-currency row caught on the second run.
        snaked = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", text)
        tokens = set(re.split(r"[^a-z0-9]+", snaked.lower()))
        found |= {p for p in products if p in tokens}
    return found


def _core_modules() -> list[Path]:
    return sorted(p for p in CORE.rglob("*.py") if "__pycache__" not in p.parts)


def test_no_core_module_names_a_managed_product() -> None:
    """The claim in full: adding Terraform knowledge to this platform touches no core file."""
    offenders = {
        str(path.relative_to(CORE)): sorted(named)
        for path in _core_modules()
        if (named := _named_in_code(path, MANAGED_PRODUCTS))
    }
    assert not offenders, (
        f"core modules name a managed product: {offenders}. Product knowledge arrives "
        f"through a pack in `packs/`, never through `src/core` — that is Principle I at the "
        f"content layer, and it is what makes 'new products are new packs' true"
    )


def test_substrate_names_appear_only_where_declared() -> None:
    """Vault and Nomad are permitted, in named modules, for a stated reason.

    Not a relaxation: the core reaching Vault for its own credential is the opposite of the
    core knowing Vault as a product. The allowlist keeps that distinction a decision rather
    than an accident, and an unlisted module naming the substrate fails here.
    """
    offenders = {
        relative: sorted(named)
        for path in _core_modules()
        if (relative := str(path.relative_to(CORE))) not in SUBSTRATE_ALLOWED
        and (named := _named_in_code(path, SUBSTRATE))
    }
    assert not offenders, (
        f"these name the substrate without being on the allowlist: {offenders}. Add the "
        f"module with its reason, or route the access through the fabric seam"
    )


def test_every_allowlist_entry_still_needs_its_exemption() -> None:
    """An allowlist entry for a module that no longer qualifies is an allowlist that lies."""
    for relative in SUBSTRATE_ALLOWED:
        path = CORE / relative
        assert path.is_file(), f"allowlist names {relative}, which does not exist"
        assert _named_in_code(path, SUBSTRATE), (
            f"{relative} no longer names the substrate; remove it from SUBSTRATE_ALLOWED "
            f"rather than leaving an exemption nothing needs"
        )


def test_the_check_fires_on_a_contrived_violation(tmp_path: Path) -> None:
    """A positive control. An absence check nobody has seen fire proves nothing."""
    offender = tmp_path / "leaked.py"
    offender.write_text(
        '"""A docstring mentioning terraform is fine."""\nTOOL = "terraform_apply"\n'
    )
    assert _named_in_code(offender, MANAGED_PRODUCTS) == {"terraform"}

    prose_only = tmp_path / "prose.py"
    prose_only.write_text(
        '"""Discusses terraform at length."""\n# and a terraform comment\nX = 1\n'
    )
    assert _named_in_code(prose_only, MANAGED_PRODUCTS) == set()


def test_adding_a_pack_requires_no_core_edit() -> None:
    """SC-002's second clause — **structurally, because the diff form does not survive squash.**

    This row used to find the commit that added `packs/vault/pack.toml` and assert it touched
    no `src/core/`. That passed on the feature branch, where the pack-adding commit touched
    only `packs/` and `specs/`, and **failed the moment 013 squash-merged**: one commit now
    contains both the packs and the core support they load through, so the lookup returns a
    commit that necessarily changed core. The row asserted a property of *branch topology*,
    and squash-merge destroys branch topology.

    The property SC-002 actually promises is that **adding a product is a content change**.
    That is a fact about the mechanism, not about history, and it is checkable now: pack
    discovery enumerates a directory. A new pack is a new directory with a manifest, so no
    module has to learn its name — which is the same claim the diff was reaching for, asserted
    where it cannot be invalidated by how a branch was merged.
    """
    loader_source = (CORE / "packs" / "loader.py").read_text()
    tree = ast.parse(loader_source)

    available = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "available"
        and any(isinstance(n, ast.Attribute) and n.attr == "iterdir" for n in ast.walk(node))
    )
    assert available is not None, (
        "the filesystem loader no longer discovers packs by enumerating a directory. If pack "
        "names are now listed somewhere, adding a product is a code change and SC-002 is false"
    )

    # And the negative half: no pack name appears in the discovery path at all.
    discovered_names = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    for pack in ("vault", "terraform"):
        assert pack not in discovered_names, (
            f"the loader names {pack!r} as a literal; discovery must not know which packs exist"
        )


def test_the_diff_form_of_sc002_is_recorded_as_owed() -> None:
    """The stronger claim, and why it is not asserted here.

    "Adding the second pack changed no core file, shown by the diff" is only demonstrable by a
    commit that adds a pack **without** adding pack support — and no such commit exists yet,
    because 013 introduced both together. Asserting it against the feature-introducing commit
    is what broke; asserting it against a commit that does not exist would be worse.

    So it is **owed**, not stubbed (ADR-0047), and this row fails if the conformance contract
    stops saying so — which is the moment the next pack lands and the diff form becomes real.
    """
    contract = (
        ROOT / "specs" / "013-capability-packs" / "contracts" / "conformance-packs.md"
    ).read_text()
    assert "diff form of SC-002" in contract, (
        "the conformance contract no longer records the diff form of SC-002 as owed. If a pack "
        "has landed separately from pack support, write the diff assertion and delete this row"
    )
