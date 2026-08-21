# SPDX-License-Identifier: Apache-2.0
"""The property detector must be able to fail (041, T019).

**This file is what makes the detector trustworthy, and without it the live qualification would
be worthless.** A detector that returns every property for every artefact qualifies any model
for anything — the un-loseable gate this repository refuses, wearing a scorer's clothes.

The corpus supplies the falsifying case itself. `static_credential_lookalike` asks for exactly
what `dynamic_database_secret` asks for and answers it with a long-lived credential in
configuration: it parses, `terraform validate` is happy, and it is the wrong answer. Gate one
passes it. **This detector must fail it**, and the row below is that requirement.
"""

from __future__ import annotations

from tests.evals_live.authoring_properties import detect

# The shape a correct answer takes: read from the store, no literal, leased.
RIGHT = {
    "main.tf": """
data "vault_generic_secret" "db" {
  path = "database/creds/app"
}

resource "app_config" "main" {
  username = data.vault_generic_secret.db.data["username"]
  password = data.vault_generic_secret.db.data["password"]
}
"""
}

# ADR-0038's warning case, and the corpus's `valid_but_wrong = true`: syntactically fine,
# substantively wrong. A long-lived credential sitting in configuration.
SUBTLY_WRONG = {
    "main.tf": """
resource "app_config" "main" {
  username = "app_user"
  password = "s3cr3t-long-lived-value"
}
"""
}


def test_the_detector_recognises_a_correct_answer() -> None:
    found = detect(RIGHT)
    assert "reads_credentials_from_secret_store" in found
    assert "no_literal_credential_in_source" in found
    assert "credential_has_a_lease" in found


def test_the_detector_FAILS_the_valid_but_wrong_case() -> None:
    """The row this whole file exists for.

    If this ever passes, the live qualification is measuring nothing and every cell it
    promoted is unearned.
    """
    found = detect(SUBTLY_WRONG)

    assert "reads_credentials_from_secret_store" not in found, (
        "a literal credential in configuration is not a read from the secret store"
    )
    assert "credential_has_a_lease" not in found, "a hardcoded password does not expire"
    assert "no_literal_credential_in_source" not in found, (
        "the literal IS in the source; a detector that missed it would pass ADR-0038's own "
        "warning case, which is the failure mode this corpus exists to catch"
    )


def test_score_reference_rejects_the_subtly_wrong_artefact() -> None:
    """End to end through the real scorer, not just the detector."""
    from pathlib import Path

    from core.evals.authoring_corpus import load_corpus
    from core.evals.authoring_scoring import score_reference

    corpus = load_corpus(
        Path(__file__).resolve().parents[2] / "evals" / "authoring" / "corpus.toml"
    )
    task = next(t for t in corpus.golden if t.name == "static_credential_lookalike")

    assert not score_reference(task, detect(SUBTLY_WRONG))
    assert score_reference(task, detect(RIGHT))


def test_an_empty_artefact_exhibits_nothing() -> None:
    """`existing_integration_is_not_duplicated` expects no artefact, and no properties."""
    assert detect({}) == frozenset()


def test_a_floating_constraint_is_not_a_pin() -> None:
    """`>=` / `*` have no ceiling. HashiCorp `~>` does — the style guide's own pin."""
    assert "provider_version_is_pinned" not in detect({"v.tf": 'version = ">= 4.0"'})
    assert "no_floating_version_constraint" not in detect({"v.tf": 'version = ">= 4.0"'})
    assert "provider_version_is_pinned" not in detect({"v.tf": 'version = "*"'})
    assert "provider_version_is_pinned" in detect({"v.tf": 'version = "4.2.1"'})
    assert "no_floating_version_constraint" in detect({"v.tf": 'version = "4.2.1"'})


def test_a_hashicorp_pessimistic_constraint_is_a_pin() -> None:
    found = detect({"v.tf": 'version = "~> 4.0"'})
    assert "provider_version_is_pinned" in found
    assert "no_floating_version_constraint" in found
    patch = detect({"v.tf": 'version = "~> 4.4.0"'})
    assert "provider_version_is_pinned" in patch
    mixed = detect({"v.tf": 'version = "~> 4.0"\nversion = ">= 1.0"'})
    assert "provider_version_is_pinned" not in mixed
    assert "no_floating_version_constraint" not in mixed


def test_a_wildcard_capability_is_detected() -> None:
    wild = {"p.tf": 'path "secret/*" {\n  capabilities = ["read", "*"]\n}'}
    assert "no_wildcard_capability" not in detect(wild)

    scoped = {"p.tf": 'path "secret/data/app" {\n  capabilities = ["read"]\n}'}
    assert "no_wildcard_capability" in detect(scoped)
    assert "policy_scoped_to_one_path" in detect(scoped)


def test_two_paths_are_not_one_path() -> None:
    two = {
        "p.tf": (
            'path "secret/data/app" {\n  capabilities = ["read"]\n}\n'
            'path "secret/data/other" {\n  capabilities = ["read"]\n}'
        )
    }
    assert "policy_scoped_to_one_path" not in detect(two)


def test_an_interpolated_password_is_not_a_literal() -> None:
    """The correct answer assigns a password; what matters is where it comes from."""
    interpolated = {"m.tf": 'password = data.vault_generic_secret.db.data["password"]'}
    assert "no_literal_credential_in_source" in detect(interpolated)


def test_every_property_the_corpus_names_is_detectable() -> None:
    """A property no detector can produce makes its task impossible to pass.

    The corpus is human-authored and this module is not; a name added there and not here would
    silently fail every future qualification, and the failure would look like a bad model.
    """
    from pathlib import Path

    import tests.evals_live.authoring_properties as detector

    from core.evals.authoring_corpus import load_corpus

    corpus = load_corpus(
        Path(__file__).resolve().parents[2] / "evals" / "authoring" / "corpus.toml"
    )
    named: set[str] = set()
    for task in corpus.golden:
        if task.reference is not None:
            named |= set(task.reference.properties)

    source = (Path(detector.__file__)).read_text()
    missing = sorted(name for name in named if f'"{name}"' not in source)
    assert not missing, (
        f"the corpus names {missing}, which this detector can never produce — every task "
        f"requiring one is unpassable, and the failure would read as the model's fault"
    )
