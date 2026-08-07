# SPDX-License-Identifier: Apache-2.0
"""Detecting the properties the corpus's references declare (041, T019).

**The corpus names the standard; this implements detection of it.** `evals/authoring/corpus.toml`
records a human author against every reference precisely so the properties are not invented by
whatever grades them. Nothing here decides what "correct" means — Dan's references do — and this
module only answers whether a given artefact exhibits a named property.

**It must be able to fail, and the corpus supplies the case that proves it.**
`static_credential_lookalike` asks for the same thing as `dynamic_database_secret` and answers
it with a long-lived credential in configuration. It parses; the product's own tooling is happy.
A detector that passes it has measured nothing, so `test_authoring_properties.py` requires this
detector to fail it — that row is what makes the rest of this file trustworthy.

**Textual, deliberately.** A full HCL parse would be more precise and would also be a second
implementation of what `terraform validate` already does in gate one. Gate one catches
malformed; this gate catches *subtly wrong*, and subtly wrong is legible in the text.
"""

from __future__ import annotations

import re

#: A literal credential assigned in source: `password = "hunter2"`, `secret_key = "AKIA..."`.
#: Interpolations and data-source references are excluded — `password = var.x` or
#: `= data.vault_generic_secret.db.data["password"]` is the *right* answer, not a violation.
_LITERAL_CREDENTIAL = re.compile(
    r"""(?ix)
    \b(password|passwd|secret|secret_key|access_key|token|api_key|private_key)\b
    \s*=\s*
    "(?![\s]*$)               # a quoted literal...
    (?!\$\{)                  # ...that is not an interpolation
    [^"]{4,}"
    """
)

#: Reading from a secret store: a Vault data source, or a reference to one.
_SECRET_STORE_READ = re.compile(
    r"""(?ix)
    data\s+"vault_[a-z_]+"          # data "vault_generic_secret" "db" { ... }
    | \bdata\.vault_[a-z_]+\.       # data.vault_generic_secret.db.data[...]
    | \bvault_database_secret_backend
    """
)

#: A credential that expires: a dynamic-credentials path, or an explicit lease.
_LEASED = re.compile(
    r"""(?ix)
    /creds/                          # database/creds/app — the dynamic path
    | \bmax_ttl\b | \bdefault_ttl\b | \blease\b
    | \bvault_database_secret_backend_role\b
    """
)

#: An exact version pin: `version = "1.2.3"`. No operator, no range.
_EXACT_PIN = re.compile(r'(?i)\bversion\s*=\s*"\s*\d+\.\d+(\.\d+)?\s*"')

#: A constraint that can drift on a re-run.
_FLOATING = re.compile(r'(?i)\bversion\s*=\s*"[^"]*(>=|<=|>|<|~>|\^|\*|latest)[^"]*"')

#: A capability list containing a wildcard, or a policy path ending in one.
_WILDCARD = re.compile(
    r"""(?ix)
    capabilities\s*=\s*\[[^\]]*"\*"[^\]]*\]
    | path\s+"[^"]*\*"
    """
)

#: A Vault policy path block. Counted, because "scoped to one path" is a count.
_POLICY_PATH = re.compile(r'(?im)^\s*path\s+"[^"]+"\s*\{')


def _joined(contents: dict[str, str]) -> str:
    return "\n".join(contents.values())


def detect(contents: dict[str, str]) -> frozenset[str]:
    """Every property this artefact exhibits, by the corpus's own vocabulary.

    Returns the empty set for an empty artefact, which is what
    `existing_integration_is_not_duplicated` requires: `score_reference` treats no-artefact
    tasks as passing exactly when no property is present.
    """
    if not contents:
        return frozenset()

    text = _joined(contents)
    found: set[str] = set()

    if _SECRET_STORE_READ.search(text):
        found.add("reads_credentials_from_secret_store")
    if not _LITERAL_CREDENTIAL.search(text):
        found.add("no_literal_credential_in_source")
    if _LEASED.search(text):
        found.add("credential_has_a_lease")

    if _EXACT_PIN.search(text) and not _FLOATING.search(text):
        found.add("provider_version_is_pinned")
    if not _FLOATING.search(text):
        found.add("no_floating_version_constraint")

    paths = _POLICY_PATH.findall(text)
    if len(paths) == 1:
        found.add("policy_scoped_to_one_path")
    if not _WILDCARD.search(text):
        found.add("no_wildcard_capability")

    return frozenset(found)


__all__ = ["detect"]
