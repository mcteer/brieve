# SPDX-License-Identifier: Apache-2.0
"""GATE:no-secret-leak — FR-003, asserted as an absence.

A negative requirement cannot be proven by something passing, so this enumerates every
authentication path in the surface and asserts what is **not** there.

**Comments and docstrings are stripped before matching.** Prose about API keys is not an
API key, and this file necessarily contains a great deal of prose about API keys. This
repository has now had five checks match a comment instead of code — 006's boundary
checker, 007's run-reference check, 024's read-path isolation test, 020's conformance-marker
check, and the provider-key row — so the stripping is not defensive tidiness, it is the whole
reliability of the check. The stripper itself moved to `tests/harness/source_reading.py` at
the fifth occurrence; the rows below still exercise it, because it is load-bearing here.
"""

from __future__ import annotations

import pathlib

from tests.harness.source_reading import code_without_prose

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

#: The one module permitted to name a vendor key's field, and the one term it may name.
#:
#: **027 amended this gate in the open, in the same change that amended the constitution**, and
#: for the same reason: the platform now holds a model vendor credential, so a check asserting it
#: holds none anywhere would be a check asserting something untrue. The alternative considered and
#: rejected was renaming the KV field to something the matcher does not know — which would have
#: left the gate green while the credential existed, and a gate that passes by vocabulary is worse
#: than no gate.
#:
#: **What the exception deliberately does not cover.** It is one module, one term. Every surface
#: module still fails on any of these names, which is why `ModelCredential.secret` is called
#: `secret`: the brokered key crosses into `served.py` inside a value object and is handed
#: straight to a provider constructor, so a surface that started *holding* one would trip this
#: gate exactly as before. The lifetime property — fetched per task, never persisted — is not
#: visible to a name check and is asserted where it is observable, at the trail and the
#: checkpoint (027 T016).
EXEMPT: dict[str, frozenset[str]] = {
    "model_credential.py": frozenset({"api_key"}),
}


#: Shared rather than kept here (027). This file grew the first stripper; by the fifth check to
#: match prose instead of code it was clear the next one would need it too, and two copies means
#: fixing the sixth occurrence twice. The rows below still exercise it, because it is load-bearing
#: for this gate whoever owns it.
_code_without_prose = code_without_prose


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
        allowed = EXEMPT.get(path.name, frozenset())
        for name in FORBIDDEN:
            if name in code and name not in allowed:
                offenders.append(f"{path.name}: {name}")
    assert offenders == [], f"static credential paths present: {offenders}"


def test_the_exemption_stays_exactly_one_module_and_one_term() -> None:
    """The exemption is a named exception, and a named exception that grows is not one.

    Pinned by count so a second module or a second term cannot be added quietly — the same
    discipline the constitution's *"exactly two named exceptions"* clause applies one level up.
    Whoever needs a third comes here, changes this number, and says why.
    """
    assert list(EXEMPT) == ["model_credential.py"]
    assert EXEMPT["model_credential.py"] == frozenset({"api_key"})


def test_the_exempt_module_exists_and_still_names_the_term() -> None:
    """A stale exemption is a hole nobody is watching.

    If `model_credential.py` is renamed, deleted, or stops naming the field, this fails and the
    exemption is removed rather than left standing over nothing.
    """
    exempt = [p for p in _surface_sources() if p.name == "model_credential.py"]
    assert len(exempt) == 1, "the exempt module moved; the exemption must move or go"
    assert "api_key" in _code_without_prose(exempt[0]).lower()


def test_no_surface_module_names_a_vendor_key_even_now_that_one_exists() -> None:
    """The half of the gate 027 must not cost, asserted separately so it cannot erode.

    The brokered key crosses `served.py` inside a `ModelCredential` and goes straight into a
    provider constructor; no surface names it, holds it as an attribute, or logs it. This row
    scopes the original assertion to `src/surfaces/` alone, with **no exemption at all** — so if
    the exemption above is ever widened to cover a surface module, this fails first.
    """
    offenders = [
        f"{path.relative_to(SURFACES)}: {name}"
        for path in sorted(SURFACES.rglob("*.py"))
        for name in FORBIDDEN
        if name in _code_without_prose(path).lower()
    ]
    assert offenders == [], f"a surface module names a static credential: {offenders}"


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
