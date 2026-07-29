# SPDX-License-Identifier: Apache-2.0
"""Threads — a readable view over what the trail already records.

**The organizing rule, from ADR-0051: the trail is the record; these tables are a view.**
Everything in this package is shaped by which side of that line it sits on, and the line
is what makes two requirements true at once — a person may delete a conversation
(FR-010b), and evidence may never be masked (ADR-0035). Both hold because deleting a
reading of a record removes no record.

That has a consequence worth stating where someone will read it before changing anything:
**a turn's audit event is written before its row.** Not for tidiness — a row written first
could survive a crash with no event behind it, and then the view would assert something
the trail cannot support, which is the one direction this design does not permit. The
reverse (an event with no row) is expected: on a deleted thread it is the whole point, and
on a live one it is the crash window between the two writes, where the trail's account
wins.

**Deliberately not `core.runs`.** That package answers "what have I started" — operational
records *about* runs. This one holds what a person *said*, which is evidence with a
different lifetime, a different deletion posture, and a different reason to exist. Placing
them together would invite a later change to give threads the run index's
never-deleted rule, or give the run index this package's deletable one, and both would be
wrong.

**Nothing here is on the resume path**, so all of it is droppable — the same property
`core.runs` protects, for the same reason.
"""
