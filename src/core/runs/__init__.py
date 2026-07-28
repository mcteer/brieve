# SPDX-License-Identifier: Apache-2.0
"""Operational records about runs — enumeration, not durability.

**Deliberately not `core.durability`.** Everything here answers a question a *person* asks
("what have I started", "was my change approved"); durability answers a question the
*platform* asks ("where did this run get to"). Placing these beside checkpoints would
invite the widening that research F1 rejected — resume does not need a subject, and a
resume-critical table should not grow columns only a listing reads.

The consequence worth keeping: nothing in this package is on the resume path, so all of it
is droppable. A run index that resume read would stop being droppable, and droppable is
worth protecting for a table whose only job is enumeration.

**A recorded open question, not a decision.** `suspended_runs` (009) and `run_index` (011)
are both "find runs by something other than their id". Two indexes over one run population
is a coherence question, and it is deliberately unresolved here — nothing forces it yet,
and merging them speculatively would couple the sweeper's candidate list to a product read
path for no reason anyone can currently name.
"""
