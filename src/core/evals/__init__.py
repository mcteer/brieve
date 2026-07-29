# SPDX-License-Identifier: Apache-2.0
"""Eval gates — Principle VIII's machinery, brought online for the first time.

**Gates are records, not claims.** A cell is qualified because a suite ran and a result was
written, and the result is retrievable. "We evaluated it" is not a thing this package can
express.

**Nothing on the run path imports this package.** A matrix cell is an *authorization fact* —
it says a definition may use a model for a role — so the reader lives in
`core.authority.matrix` and is imported at every run start. This package *writes* cells
through that module; the scoring harness, the suites, and the judges are never reachable
from a run. That layering is asserted by
`tests/conformance/packs/test_run_path_does_not_import_evals.py` rather than trusted to
naming, because a module in a package called `evals` sitting on the run path is exactly the
invitation somebody eventually accepts.

**The blocking lane scores recordings.** `FixtureScorer` replays a recorded response and
imports no provider SDK; `LiveModelScorer` calls a real model and runs only behind
`@pytest.mark.live_model`. The suites, the thresholds, and the refusals are identical across
both — only the scorer differs, which is what makes "the machinery is real even when the
substrate is a recording" true rather than aspirational.

**A cell qualified against a fixture is qualified against a recording**, and the per-cell
record in `contracts/conformance-packs.md` is where that stops being invisible.
"""
