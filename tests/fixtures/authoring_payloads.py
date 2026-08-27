# SPDX-License-Identifier: Apache-2.0
"""A checkpoint payload shaped exactly as an authoring run writes one (052, T001/T002).

**Shaped from `proposal_payload`, not invented.** Every key here is one that function writes,
in the same nesting, so a row asserting "the scrub kept `provenance`" is asserting something
about the record the platform actually stores rather than about a convenient stand-in.

**Bodies are the harness marker.** `AUTHORING_SUBJECT_SECRET_MARKER` is deliberately absurd
rather than plausible: a credential-shaped literal in this tree is a scanner finding whether or
not it is real, and gitleaks caught exactly that on 051's first commit attempt. Here it does
double duty — it is what a sweep looks for, so a row can assert the marker is gone from the
store rather than assert an absence of nothing.
"""

from __future__ import annotations

import hashlib
from typing import Any

from tests.harness.secrets import AUTHORING_SUBJECT_SECRET_MARKER

#: The two files the fixture run authored, with the digests its provenance records.
#:
#: Digests are computed rather than written down, so the manifest and the bodies cannot drift
#: apart in the fixture itself — which is the very thing row A3 asserts about the scrub.
FILES: tuple[tuple[str, str, bool], ...] = (
    (
        "src/config/vaultConfig.js",
        f"// {AUTHORING_SUBJECT_SECRET_MARKER}\n"
        "module.exports = { addr: process.env.VAULT_ADDR };\n",
        False,
    ),
    (
        "main.tf",
        f"# {AUTHORING_SUBJECT_SECRET_MARKER}\n"
        'resource "aws_vpc" "main" {\n  cidr_block = "10.0.0.0/16"\n}\n',
        True,
    ),
)

RATIONALE = (
    "Wires the application to the secret store. Derived from the subject repository, which is "
    f"why FR-032 treats this field as content: {AUTHORING_SUBJECT_SECRET_MARKER}"
)


def _digest(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


#: The `provenance` lines a real proposal carries — run, commit, consulted paths, then one
#: `path — digest` line per authored file. **This is the manifest FR-009 preserves**, and it
#: exists before this feature does.
PROVENANCE: list[str] = [
    "Run: `propose-fixture0000052`",
    "Analysed at commit `8e97b19acc596a4a6ced42af3a91449b15180e86`",
    "Consulted 1 subject path(s): `README.md`",
    *[f"`{path}` — `{_digest(body)}`" for path, body, _ in FILES],
]


def authored_payload(*, include_result: bool = True) -> dict[str, Any]:
    """A terminal checkpoint payload for a run that authored and published."""
    payload: dict[str, Any] = {
        "authoring_proposal": {
            "target_repository": "acme/infra",
            "branch": "brieve/authoring/deadbeefdeadbeef",
            "task": "Wire the application to dynamic credentials",
            "title": "Wire the application to the secret store",
            "rationale": RATIONALE,
            "usage": "Copy `.env.example` to `.env` and set VAULT_ADDR before running.",
            "disclosures": [],
            "provenance": list(PROVENANCE),
            "evidence": [],
            "state": "opened",
            "files": [
                {"path": path, "body": body, "is_diff": is_diff} for path, body, is_diff in FILES
            ],
        }
    }
    if include_result:
        # `pr_url` is the field the recorded analyzer-snapshot defect lost, and row A19 asserts
        # it survives — so the fixture has to carry it.
        payload["__run_result__"] = {
            "pr_url": "https://github.com/acme/infra/pull/7",
            "tools": ["author_file", "read_subject"],
        }
    return payload


def scrubbed_payload(*, include_result: bool = True) -> dict[str, Any]:
    """What `authored_payload()` must become. Diffed whole, not asserted key by key.

    A field-by-field assertion passes while quietly ignoring a key nobody thought to name;
    comparing against this catches a scrub that took something it should not have.
    """
    payload = authored_payload(include_result=include_result)
    proposal = payload["authoring_proposal"]
    for entry in proposal["files"]:
        entry["body"] = ""
    proposal["rationale"] = ""
    proposal["scrubbed"] = True
    return payload


def empty_payload() -> dict[str, Any]:
    """A run that authored nothing. Must take the same cleanup path as one that published."""
    return {"__run_result__": {"tools": [], "message": "already implemented"}}


__all__ = [
    "FILES",
    "PROVENANCE",
    "RATIONALE",
    "authored_payload",
    "empty_payload",
    "scrubbed_payload",
]
