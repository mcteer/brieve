# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — SC-009's second half.

`test_protocol_has_no_test_affordances.py` asserts the protocol declares nothing that
exists for tests. That is necessary and not sufficient: **a clean protocol nobody implements
is as vacuous as a dirty one everybody does.** This asserts the other side — that the
production fabric satisfies what remains, with no method raising "not supported".

Here rather than in the protocol file because the class does not exist until the ceiling,
scope, and policy resolutions land, and a row asserting a class into existence fails for a
reason that has nothing to do with what it checks.
"""

from __future__ import annotations

import inspect

from core.authority.fabric import IdentityFabric
from core.authority.vault_fabric import SubjectScopedVaultFabric, VaultIdentityFabric


def _protocol_methods() -> set[str]:
    return {
        name
        for name, value in vars(IdentityFabric).items()
        if not name.startswith("_") and callable(value)
    }


def test_the_production_fabric_implements_every_declared_method() -> None:
    declared = _protocol_methods()
    assert declared, "the protocol declares nothing, so this row would pass vacuously"

    missing = [name for name in declared if not hasattr(VaultIdentityFabric, name)]

    assert not missing, f"VaultIdentityFabric does not implement {missing}"


def test_no_method_is_a_not_supported_stub() -> None:
    """The honest implementation of a method you cannot implement is one that raises.

    So a protocol whose production implementation raises is a protocol that does not
    describe its own production case — which is exactly what the brokered-material methods
    made true before this feature removed them.
    """
    offenders: list[str] = []
    for name in _protocol_methods():
        method = getattr(VaultIdentityFabric, name, None)
        if method is None:
            continue
        try:
            source = inspect.getsource(method)
        except (OSError, TypeError):  # pragma: no cover - defensive
            continue
        lowered = source.lower()
        if "notimplementederror" in lowered or "not supported" in lowered:
            offenders.append(name)

    assert not offenders, (
        f"{offenders} raise rather than implement. A protocol whose production "
        "implementation cannot honour it is describing something else."
    )


def test_the_subject_scoped_variant_is_usable_as_the_protocol() -> None:
    """The class the run path actually constructs, not only its base.

    A base that satisfied the protocol while the subclass broke it would pass every
    assertion above and fail at the only call site that matters.
    """
    fabric: IdentityFabric = SubjectScopedVaultFabric(
        roles=["operator"],
        credentials=object(),
        known_tools=frozenset({"echo"}),
        known_actions=frozenset(),
    )

    for name in _protocol_methods():
        assert callable(getattr(fabric, name)), f"{name} is not callable on the run path's fabric"
