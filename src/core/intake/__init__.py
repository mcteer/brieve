# SPDX-License-Identifier: Apache-2.0
"""The intake gauntlet (037, ADR-0053).

Analysis starts when upstream publishes, so the reviewer reads evidence instead of raw
upstream text. **The pipeline decides what a reviewer reads, never whether a skill
promotes** — that sentence is what the whole feature is measured against, and every stage
here produces evidence for `promote_skill` rather than acting in its place.

Product-blind, like the rest of `core`: this module knows about pins, deltas and digests. It
does not know what Terraform or Vault are, and a change that taught it would be a change that
put product knowledge in the layer that is supposed to be able to govern anything.
"""

from core.intake.pins import Pin, PinState, read_pin
from core.intake.proposal import Candidate, Delta

__all__ = ["Candidate", "Delta", "Pin", "PinState", "read_pin"]
