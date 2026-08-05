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
        """The ledger FLATTENED, so the checkpoint credential scanner can see into it.

        **Measured, and the reason this method is not the obvious nested shape.** The
        adapter's `_reject_credentials` inspects *top-level keys only* — it does not walk. A
        nested payload therefore hides every credential-shaped key one level down, and a
        checkpoint row asserting "a credential is refused" would pass while a credential in a
        tool result sailed through. That is a scanner that has stopped finding things, which
        is exactly the failure this file exists to prevent (FR-011, research R9).

        So every mapping the sandbox saw is hoisted: a key anywhere in the ledger becomes a
        key here, prefixed with where it came from. Prefixes keep provenance readable without
        hiding the key itself — `_reject_credentials` matches on the key's own name, so
        `resume.0.api_key` still ends in the token it is looking for.

        Non-mapping values are carried under their own path. Nothing is dropped: a scanner
        that summarized would be one that could stop noticing.
        """
        flat: dict[str, Any] = {}

        def hoist(prefix: str, value: Any) -> None:
            if isinstance(value, dict):
                for key, inner in value.items():
                    hoist(f"{prefix}{key}" if not prefix else f"{prefix}.{key}", inner)
                    # The bare key too, so a shallow scanner matching on exact key names
                    # sees it. Provenance lives in the prefixed entry beside it.
                    if isinstance(key, str) and not isinstance(inner, dict | list):
                        flat.setdefault(key, inner)
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    hoist(f"{prefix}.{index}" if prefix else str(index), item)
            else:
                flat[prefix] = value

        hoist("inputs", dict(self.inputs))
        hoist("resume", [{"call_id": cid, "value": v} for cid, v in self.resume_values])
        return flat
