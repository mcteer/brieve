# SPDX-License-Identifier: Apache-2.0
"""046 S4 — portal renders primary_answer first; legacy claims[] still replay."""

from __future__ import annotations

from typing import Any

from fastapi.templating import Jinja2Templates

from surfaces.portal.app import TEMPLATES
from surfaces.portal.relay import ApiResponse

_TEMPLATES = Jinja2Templates(directory=str(TEMPLATES))


def _render(payload: dict[str, Any]) -> str:
    return _TEMPLATES.get_template("_outcome.html").render(
        response=ApiResponse(status=200, payload=payload)
    )


def test_primary_answer_renders_before_supporting_citations() -> None:
    html = _render(
        {
            "disposition": "answered",
            "source": "guidance",
            "primary_answer": "A Vault cluster spans availability zones.",
            "citations": [
                {
                    "url": "https://developer.hashicorp.com/patterns/vault/clustering#clustering",
                    "provenance": "validated-design",
                }
            ],
        }
    )

    assert "primary-answer" in html
    assert "A Vault cluster spans availability zones." in html
    assert html.index("primary-answer") < html.index("citations")
    assert 'class="claims"' not in html


def test_legacy_claims_outcomes_still_render() -> None:
    html = _render(
        {
            "disposition": "answered",
            "source": "guidance",
            "claims": [
                {
                    "statement": "A Vault cluster spans availability zones.",
                    "citations": [
                        "https://developer.hashicorp.com/patterns/vault/clustering#clustering"
                    ],
                }
            ],
        }
    )

    assert "A Vault cluster spans availability zones." in html
    assert 'class="claims"' in html
