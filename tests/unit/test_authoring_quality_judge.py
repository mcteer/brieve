# SPDX-License-Identifier: Apache-2.0
"""Authoring Judge picks a distinct live model (047, ADR-0067)."""

from __future__ import annotations

from types import SimpleNamespace

from surfaces.dispatch.entrypoint import _distinct_live_judge_model, _judge_chooser_for


def _fabric(cells: list[dict[str, object]]) -> SimpleNamespace:
    return SimpleNamespace(read_matrix=lambda: {"schema_version": 1, "cells": cells})


def test_distinct_live_judge_prefers_opus_over_writer() -> None:
    fabric = _fabric(
        [
            {
                "pack": "vault",
                "model": "anthropic/claude-sonnet@5",
                "role": "judge",
                "qualified_by": "live",
                "judge": "seed",
            },
            {
                "pack": "vault",
                "model": "anthropic/claude-opus@5",
                "role": "judge",
                "qualified_by": "live",
                "judge": "seed",
            },
        ]
    )
    assert (
        _distinct_live_judge_model(fabric, write_model="anthropic/claude-sonnet@5")
        == "anthropic/claude-opus@5"
    )


def test_distinct_live_judge_skips_the_write_model() -> None:
    fabric = _fabric(
        [
            {
                "pack": "vault",
                "model": "anthropic/claude-sonnet@5",
                "role": "judge",
                "qualified_by": "live",
                "judge": "seed",
            },
        ]
    )
    assert _distinct_live_judge_model(fabric, write_model="anthropic/claude-sonnet@5") == ""


def test_judge_chooser_skipped_for_fixture_write() -> None:
    chooser, model = _judge_chooser_for(
        identity_fabric=_fabric([]),
        audit_sink=None,
        correlation_id="c",
        tenant_id="t",
        agent_definition_id="authoring-agent",
        run_id="r",
        write_model="fixture/scripted@1",
    )
    assert chooser is None
    assert model == ""
