# SPDX-License-Identifier: Apache-2.0
"""What entered the sandbox, in a form the credential discipline can read (036, FR-011).

**Why a ledger and not just the runtime's snapshot.** Suspending a program produces opaque
bytes — a serialized interpreter, in a format owned by a `0.0.x` upstream. The
credential-free-checkpoint discipline (ADR-0026) has to scan what is being persisted, and
scanning those bytes would mean parsing a format that is explicitly unstable. Worse, it
would make the platform's guarantee depend on continuing to parse it correctly: a format
change would not fail loudly, it would silently stop finding things.

So the seam keeps its own record of every value that crossed into the sandbox and every
value it resumed with. That is what the checkpoint scanner reads. It is a **parallel**
record, not a replacement — the snapshot bytes still travel, they are simply not the thing
the discipline is asserted against.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SandboxLedger:
    """Every value the platform put into a program, and every result it handed back.

    Deliberately holds values rather than digests: the point is for the checkpoint
    scanner to *find* a credential that should not be there, and a digest would hide
    exactly what it is meant to reveal.
    """

    #: What the program was started with — the inputs the platform supplied.
    inputs: dict[str, Any] = field(default_factory=dict)
    #: Every value handed back into the sandbox, in order, keyed by the call it answered.
    #: A governed tool result travels through here, which is the whole reason this must be
    #: scannable: the discipline's job is to catch a credential a tool returned before it
    #: reaches a checkpoint.
    resume_values: list[tuple[str, Any]] = field(default_factory=list)

    def record_input(self, name: str, value: Any) -> None:
        self.inputs[name] = value

    def record_resume(self, call_id: str, value: Any) -> None:
        self.resume_values.append((call_id, value))

    def scannable(self) -> dict[str, Any]:
        """The ledger as a plain mapping, for the checkpoint credential scanner.

        Shaped for `_reject_credentials`, which walks a payload looking for values that
        look like credentials. Returning a nested structure rather than a flattened one
        keeps the scan honest — a flattener that dropped a level would be a scanner that
        stopped finding things, which is the failure this whole file exists to avoid.
        """
        return {
            "inputs": dict(self.inputs),
            "resume_values": [{"call_id": cid, "value": v} for cid, v in self.resume_values],
        }
