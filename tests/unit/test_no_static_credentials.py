# SPDX-License-Identifier: Apache-2.0
"""GATE:no-secret-leak — FR-003, asserted as an absence.

A negative requirement cannot be proven by something passing, so this enumerates every
authentication path in the surface and asserts what is **not** there.

**Comments and docstrings are stripped before matching.** Prose about API keys is not an
API key, and this file necessarily contains a great deal of prose about API keys. This
repository has now had three checks match a comment instead of code — 006's boundary
checker, 007's run-reference check, and this feature's own read-path isolation test — so
the stripping is not defensive tidiness, it is the whole reliability of the check.
"""

from __future__ import annotations

import ast
import pathlib

SURFACES = pathlib.Path(__file__).resolve().parents[2] / "src" / "surfaces"

#: Names that would indicate a platform-issued or platform-accepted long-lived credential.
#: `api_key` and friends are the shapes someone reaches for when adding "just one" path
#: for automation.
#: The authority package, added by 010 — see `_surface_sources`.
AUTHORITY = pathlib.Path(__file__).resolve().parents[2] / "src" / "core" / "authority"

FORBIDDEN = (
    "api_key",
    "apikey",
    "static_token",
    "shared_secret",
    "client_secret",
    "service_account_key",
    "personal_access_token",
)


def _code_without_prose(path: pathlib.Path) -> str:
    """Return the module's source with docstrings and comments removed.

    `ast.unparse` of a parsed module drops comments entirely and lets us strip docstring
    expressions explicitly, so what remains is code and string literals that actually
    participate in behaviour.
    """
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", [])
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def _surface_sources() -> list[pathlib.Path]:
    """Surfaces, plus the authority package, as of 010.

    The identity fabric is the newest thing in this platform that could hold a credential
    and the one with the strongest reason to: it authenticates to the trust fabric on every
    step, and a cached token would be the obvious optimisation. It authenticates by
    presenting an attested workload identity instead, and this is what keeps it that way.
    """
    return sorted(SURFACES.rglob("*.py")) + sorted(AUTHORITY.rglob("*.py"))


def test_the_check_has_something_to_check() -> None:
    """Guard against the check silently covering nothing.

    Without this, deleting or moving src/surfaces would make every assertion below pass.
    """
    assert len(_surface_sources()) >= 5


def test_no_static_credential_appears_in_any_surface_module() -> None:
    offenders: list[str] = []
    for path in _surface_sources():
        code = _code_without_prose(path).lower()
        for name in FORBIDDEN:
            if name in code:
                offenders.append(f"{path.name}: {name}")
    assert offenders == [], f"static credential paths present: {offenders}"


def test_stripping_actually_works() -> None:
    """The stripper is load-bearing, so it gets its own test.

    If it stopped removing prose, the assertion above would fail on this repository's own
    documentation and someone would 'fix' it by weakening the check.
    """
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write('"""A docstring mentioning api_key."""\n# a comment mentioning api_key\nx = 1\n')
        temp = pathlib.Path(fh.name)
    try:
        assert "api_key" not in _code_without_prose(temp)
    finally:
        temp.unlink()


def test_the_stripper_does_not_hide_real_code() -> None:
    """The complement of the test above, and the more important half.

    A stripper that removed everything would make the whole gate vacuous while looking
    like it worked.
    """
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write('"""Docstring."""\napi_key = "real-code"\n')
        temp = pathlib.Path(fh.name)
    try:
        assert "api_key" in _code_without_prose(temp)
    finally:
        temp.unlink()


def test_only_two_authentication_mechanisms_exist() -> None:
    """FR-002/FR-003: a human identity or a federated workload identity, and no third.

    Asserted against the composite verifier's own subject kinds rather than by reading
    prose, so adding a third branch is what fails rather than describing one.
    """
    from core.identity.types import SubjectKind

    assert {k.value for k in SubjectKind} == {"human", "workload"}
