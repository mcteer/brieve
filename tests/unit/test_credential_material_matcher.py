# SPDX-License-Identifier: Apache-2.0
"""The no-secret sweeps' matcher, and proof it can still fail (2026-08-27).

Both durability sweeps — the blob-level one from 005 and the live-table one from 014 — asked
whether a rendered row contained any of `credential`, `token`, `secret`, `password`. As bare
substrings. A Judge model's own prose then said *"the slice is on-topic and secret-free"*, and
the gate proving the state store holds no authority went red because a model used the word
while reporting the absence of the thing.

**Loosening a gate is only defensible if the gate can still catch what it is for**, so the
positive rows below matter more than the negative ones. Each plants a shape a real leak would
take and requires the matcher to find it. Without them this file would be evidence that the
sweeps had been quietened rather than corrected.

The rule the fix encodes: **a credential in a store is a value under a key.**
`"vault_token": "hvs.CAESIJ..."` is a leak; `secret-free` in a sentence is not, and no amount
of prose can become one.
"""

from __future__ import annotations

import pytest
from tests.conformance.durability.rows import (
    CREDENTIAL_FIELDS,
    CREDENTIAL_MARKERS,
    credential_material_in,
)
from tests.harness.secrets import SECRET_MARKER

#: Shapes a real leak takes. The matcher must find every one.
#:
#: **VALUES ARE THE HARNESS MARKER, never credential-shaped literals.** The first version of
#: this file wrote plausible ones — `hvs.CAESIJ0dV3xq`, `sup3r-secret` — and the gitleaks hook
#: found five on the first commit attempt. `AGENTS.md` says it plainly: never write secrets
#: anywhere, *including plausible-looking fake ones*, because a credential-shaped string in
#: this tree is a finding whether or not it is real, and "it was only a fixture" is what you
#: learn after the alert. `tests/harness/secrets.py` records 038 learning the same thing.
#:
#: The matcher does not care what the value is — only that a credential-named key has a
#: non-empty one — so an absurd marker exercises it exactly as well as a realistic string.
LEAKS = {
    "vault token value": f'{{"vault_token": "{SECRET_MARKER}"}}',
    "bare token field": f'{{"token": "{SECRET_MARKER}"}}',
    "python repr secret": f"{{'client_secret': '{SECRET_MARKER}'}}",
    "nested credential": f'{{"grant": {{"credential": "{SECRET_MARKER}"}}}}',
    "password field": f'{{"password": "{SECRET_MARKER}"}}',
    "api key with prefix": f'{{"anthropic_api_key": "{SECRET_MARKER}"}}',
    "private key field": f'{{"private_key": "{SECRET_MARKER}"}}',
    "run salt": f'{{"run_salt": "{SECRET_MARKER}"}}',
    "equals form": f"client_secret = '{SECRET_MARKER}'",
    # The two structural markers carry no value at all — they ARE the signal.
    "PEM header": "-----BEGIN RSA PRIVATE KEY-----",
    "vault token prefix": "hvs." + SECRET_MARKER,
    "vault batch prefix": "hvb." + SECRET_MARKER,
}

#: Text that must NOT match. Every one is prose a model or a person could legitimately write.
INNOCENT = {
    "the judge's actual words": (
        "The slice is on-topic and secret-free, but it does not hang together as valid "
        "Terraform: main.tf and networking.tf both declare the same data source"
    ),
    "prose about tokens": "the tool returns a token to the loop, which the adapter counts",
    "prose about credentials": "no standing credential is held by the enclave",
    "a field name with no value": '{"token": ""}',
    "a null field": '{"credential": null}',
    "documentation sentence": "Never write a password into a .tf file or a committed .tfvars",
    "a path that mentions secrets": '{"path": "secret/data/app"}',
    "reason code": '{"stop_reason": "secret_in_output"}',
}


@pytest.mark.parametrize("name", sorted(LEAKS))
def test_a_real_leak_is_caught(name: str) -> None:
    """THE ROWS THAT MAKE THE FIX HONEST. A matcher that caught none of these is not a gate."""
    assert credential_material_in(LEAKS[name]) is not None, LEAKS[name]


@pytest.mark.parametrize("name", sorted(INNOCENT))
def test_prose_is_not_a_leak(name: str) -> None:
    assert credential_material_in(INNOCENT[name]) is None, INNOCENT[name]


def test_the_judges_sentence_was_the_actual_failure() -> None:
    """Named exactly, so the regression is recognisable if it returns.

    This sentence was written by a Judge model into a real checkpoint
    (`propose-0db98c51d549e674`) and held the durability lane red across two features.
    """
    sentence = "The slice is on-topic and secret-free"
    assert "secret" in sentence.lower(), "the sentence no longer contains the trigger word"
    assert credential_material_in(sentence) is None


def test_every_field_name_is_reachable() -> None:
    """A field in the list that no pattern can match would be decoration."""
    for field in CREDENTIAL_FIELDS:
        assert credential_material_in(f'{{"{field}": "{SECRET_MARKER}"}}') is not None, field


def test_every_marker_is_reachable() -> None:
    for marker in CREDENTIAL_MARKERS:
        assert credential_material_in(f"prefix {marker} suffix") is not None, marker


def test_the_two_sweeps_share_one_definition() -> None:
    """They had drifted while a comment said they could not.

    `test_dispatched_no_secret_sweep` carried a seven-entry tuple and `rows.py` a five-entry
    one — `hvs.` and `private_key` in one copy only — under a docstring asserting the two
    could not disagree.
    """
    from pathlib import Path

    sweep = (
        Path(__file__).resolve().parents[1]
        / "conformance"
        / "durability"
        / "test_dispatched_no_secret_sweep.py"
    ).read_text(encoding="utf-8")
    assert "credential_material_in" in sweep
    restated = '"secret", "password"'
    assert restated not in sweep, "the sweep restates the list instead of importing it"


def test_the_acceptance_row_still_matches_shapes_not_words() -> None:
    """FR-014 (052). Confirming the sweep PASSES says nothing about how it decides.

    #219 stayed hidden for three weeks because the row matched the English word "secret" in a
    Judge model's prose. A revert to substring matching would go green against a scrubbed store
    and re-open exactly that blindness, with nothing else noticing.
    """
    from pathlib import Path

    sweep = (
        Path(__file__).resolve().parents[1]
        / "conformance"
        / "durability"
        / "test_dispatched_no_secret_sweep.py"
    ).read_text(encoding="utf-8")
    assert "credential_material_in" in sweep
    for word in ('"secret"', '"password"', '"token"'):
        assert f"needle {word}" not in sweep and f"[{word}]" not in sweep
