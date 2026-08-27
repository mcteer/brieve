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


def test_tooling_failed_names_the_task() -> None:
    """A 4/5 tooling score must name the miss, not hide it in a ratio."""
    from pathlib import Path

    from core.evals.authoring_corpus import load_corpus
    from core.evals.authoring_scoring import ToolingResult, score_corpus

    corpus = load_corpus(
        Path(__file__).resolve().parents[2] / "evals" / "authoring" / "corpus.toml"
    )

    def tooling(task: object, _a: object, _c: object) -> ToolingResult:
        name = getattr(task, "name", "")
        return ToolingResult(ran=True, passed=name != "pin_the_provider", detail="refused")

    report = score_corpus(
        corpus,
        tooling=tooling,
        artefacts={t.name: (None, {}) for t in corpus.golden},  # type: ignore[misc]
        properties_of=lambda t, _a, _c: (
            t.reference.properties if t.reference is not None else frozenset()
        ),
    )
    assert report.tooling_failed == ("pin_the_provider",)
    assert report.tooling_passed == report.tooling_total - 1


# --- 051, SC-002: tags_are_shared_not_ad_hoc ---------------------------------------------
#
# No valid-but-wrong corpus twin, and none is possible: the wrong answer to "add a bucket" is
# an ad-hoc tag map, which is a different artefact for the same prompt rather than a
# different task. The falsification lives here, where it can be stated exactly.

_DEFAULT_TAGS = """provider "aws" {
  region = "us-west-2"

  default_tags {
    tags = {
      ManagedBy = "Terraform"
      Project   = var.project_name
    }
  }
}
"""

_MERGED_LOCALS = """locals {
  common_tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_s3_bucket" "artifacts" {
  bucket = "${var.project_name}-artifacts"

  tags = merge(local.common_tags, {
    Name = "artifacts"
  })
}
"""

_AD_HOC = """resource "aws_s3_bucket" "artifacts" {
  bucket = "${var.project_name}-artifacts"

  tags = {
    Name        = "artifacts"
    Environment = "production"
  }
}
"""


def test_default_tags_on_the_provider_counts() -> None:
    assert "tags_are_shared_not_ad_hoc" in detect({"providers.tf": _DEFAULT_TAGS})


def test_a_locals_set_merged_into_a_resource_counts() -> None:
    """Both shapes are in the guide. Scoring only one would score a house style, not the guide."""
    assert "tags_are_shared_not_ad_hoc" in detect({"main.tf": _MERGED_LOCALS})


def test_an_ad_hoc_tag_map_does_not_count() -> None:
    """THE ROW THAT MAKES THE REST TRUSTWORTHY.

    This is tagged, it parses, `terraform validate` is happy, and it retypes the shared set
    onto one resource — which is what the guide teaches against. A detector that passes it
    would report the skill working whether or not it was delivered.
    """
    assert "tags_are_shared_not_ad_hoc" not in detect({"main.tf": _AD_HOC})


def test_an_untagged_resource_does_not_count() -> None:
    bare = 'resource "aws_s3_bucket" "artifacts" {\n  bucket = "x"\n}\n'
    assert "tags_are_shared_not_ad_hoc" not in detect({"main.tf": bare})


def test_the_write_card_does_not_teach_tagging() -> None:
    """SC-002's premise: the arms must differ on this rule.

    The card restates most of the style guide by hand. If tagging is ever added to it,
    removing the binding stops changing the output and this measurement means nothing.
    """
    from pathlib import Path

    card = (
        Path(__file__).resolve().parents[2]
        / "packs"
        / "terraform"
        / "agents"
        / "write"
        / "AGENTS.md"
    ).read_text(encoding="utf-8")
    assert "tag" not in card.lower(), (
        "the Write card now mentions tagging, so removing the binding would no longer change "
        "the output and SC-002 measures nothing. Pick a different rule."
    )


# --------------------------------------------------------- 053: the SC-002 candidate

#: One `main.tf` holding the resource, its variables and its outputs. Valid Terraform that
#: `terraform validate` accepts, and exactly what a model produces when nothing tells it where
#: declarations belong. `single_file_module` in the corpus is this shape.
PILED_INTO_MAIN = {
    "main.tf": """
variable "bucket_name" {
  type        = string
  description = "Name of the artifact bucket"
}

variable "environment" {
  type        = string
  description = "Deployment environment"
}

resource "aws_s3_bucket" "main" {
  bucket = var.bucket_name
}

output "bucket_arn" {
  description = "ARN of the bucket"
  value       = aws_s3_bucket.main.arn
}
"""
}

#: The same module, organised as the guide's File Organization table says.
ORGANISED = {
    "variables.tf": 'variable "bucket_name" {\n  type = string\n}\n',
    "main.tf": 'resource "aws_s3_bucket" "main" {\n  bucket = var.bucket_name\n}\n',
    "outputs.tf": 'output "bucket_arn" {\n  value = aws_s3_bucket.main.arn\n}\n',
}


def test_the_organisation_detector_fails_the_single_file_module() -> None:
    """THE ROW THAT MAKES 053's SC-002 CANDIDATE WORTH MEASURING.

    Following `static_credential_lookalike`: a detector that cannot fail has measured nothing,
    and the corpus supplies the falsifying case rather than a fixture invented here.

    This matters more than usual. 051's SC-002 came back level twice because both rules were
    drawn from the guide's example code — content it shows but never instructs. File
    organisation is stated in prose, twice, and 053 delegated it out of all three cards, so it
    now reaches a phase only by delivery. If the detector could not tell the two shapes apart,
    the replacement measurement would be as empty as the one it replaces.
    """
    assert "standard_file_organisation" not in detect(PILED_INTO_MAIN)
    assert "standard_file_organisation" in detect(ORGANISED)


def test_the_corpus_case_scores_the_way_the_detector_does() -> None:
    """End to end through the real scorer, as `static_credential_lookalike` does."""
    from pathlib import Path

    from core.evals.authoring_corpus import load_corpus
    from core.evals.authoring_scoring import score_reference

    corpus = load_corpus(
        Path(__file__).resolve().parents[2] / "evals" / "authoring" / "corpus.toml"
    )
    task = next(t for t in corpus.golden if t.name == "single_file_module")

    assert not score_reference(task, detect(PILED_INTO_MAIN))
    assert score_reference(task, detect(ORGANISED))


def test_an_artefact_that_declares_nothing_placeable_is_not_organised() -> None:
    """The property must not be vacuously true.

    A one-line resource change places no variable, output, local or provider. Scoring it
    `organised` would let a task that never exercises the rule report that the rule was
    followed — and SC-002 would measure the corpus rather than the skill.
    """
    assert "standard_file_organisation" not in detect(
        {"main.tf": 'resource "aws_s3_bucket" "main" {\n  bucket = "x"\n}\n'}
    )
