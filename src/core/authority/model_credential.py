# SPDX-License-Identifier: Apache-2.0
"""The credential that lets a workload call a model — held in the trust store, never by a workload.

**The platform's first brokered credential.** Principle IV names the permitted standing credentials
and says static API keys are prohibited as workload credentials; ADR-0044 says translation
federates where the product validates external identity and brokers where it cannot. A model vendor
authenticates with a static key and validates no workload identity, so models land in the broker
branch by the existing rule — and ADR-0058 amends the constitution in the open rather than reading
around it.

**Delivered, not derived** (research F2). Vault mints lesser material for products with credential
APIs; a vendor key has none, so there is nothing to derive *from*. What makes this safe is not
scope reduction but **lifetime**: the key is fetched at task start under the caller's own attested
identity, held in process for exactly one task, and never written anywhere. Revocation is a store
operation — rotate or delete, and the next task's fetch refuses.

**Never caches.** This class holds a reader and no key. Two tasks are two reads. An instance-level
cache would recreate, inside the platform, the standing credential the platform forbids.

**One read yields both the secret and its reference**, which is a correction to the planned shape.
The plan specified `fetch()` and `credential_reference()` as separate calls; separate calls are
separate reads, and a rotation landing between them would have the trail record a generation the
call did not use. On a record whose entire value is *"which rotation generation authorised this"*,
that is the one inaccuracy worth designing away.

**Lives in `authority`, not `answering`.** 025's never-acts rows forbid the answering path any
import containing `authority`, which keeps the credential structurally out of reach of the code
that uses its product: assembly obtains it and injects a built provider, and `core.answering` never
sees a store.

**The secret is called `secret`, never `api_key`**, everywhere outside this module's own store
access. `tests/unit/test_no_static_credentials.py` forbids the static-credential vocabulary in
every surface and authority module and grants this file exactly one named exception — so a key
crossing into a surface is still a gate failure, which is the property that exemption must not cost.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

from core.authority.errors import ResolutionRefused

#: Where a vendor's credential lives. KV v2, so a read of `<mount>/data/<path>` returns the secret
#: under `data` and its rotation generation under `metadata.version`.
CREDENTIAL_PATH: Final[str] = "model-credentials"

#: The field inside the record, as an operator writes it. Named rather than inferred, so a
#: malformed record refuses instead of yielding an empty string that would fail later as a vendor
#: error — the wrong cause, reported to the wrong person.
KEY_FIELD: Final[str] = "api_key"


@dataclass(frozen=True)
class ModelCredential:
    """What one task holds: the material, and the reference that goes in the trail.

    Both from a single read, so they cannot disagree. Frozen because nothing downstream has any
    business editing either half, and a mutable one would let a caller record a reference for a
    generation it did not use.
    """

    #: The vendor credential. **Passed to a provider constructor and never anywhere else** — not
    #: to a log, a checkpoint, the trail, or model context.
    secret: str

    #: ``vault:model-credentials/<vendor>@v<version>`` — a location and a rotation generation,
    #: never a value and never a hash of one. A hash of a low-entropy-format secret is an oracle.
    reference: str


class BrokeredModelCredential:
    """Reads a vendor credential for one task. Holds a reader; never holds a key.

    ``read`` takes a store path and returns the raw KV v2 body (``{"data": ..., "metadata": ...}``)
    or ``None`` when absent — the same shape `VaultIdentityFabric`'s reads produce, so assembly
    passes the fabric's reader and tests pass a dictionary. Nothing is constructed here.
    """

    def __init__(self, *, read: Callable[[str], dict[str, Any] | None]) -> None:
        self._read = read

    def obtain(self, vendor: str) -> ModelCredential:
        """The credential **for this task only**, with the reference for the record.

        Raises `ResolutionRefused`:

        - ``credential_unavailable`` — no record, or a record carrying no key. An empty key would
          reach the vendor and come back as an authentication error, reporting a credential problem
          as a vendor problem.
        - ``fabric_unreachable`` — the store itself did not answer. **Deliberately
          distinguishable**: an outage is not a governance state, and collapsing the two would
          send someone to write a credential that already exists, during an incident.
        """
        path = f"{CREDENTIAL_PATH}/data/{vendor}"
        try:
            body = self._read(path)
        except ResolutionRefused:
            raise
        except Exception as exc:  # noqa: BLE001 — any read fault is a read fault
            raise ResolutionRefused(
                f"the trust store could not be read for {vendor!r}: {type(exc).__name__}",
                reason_code="fabric_unreachable",
            ) from exc

        if not body:
            raise ResolutionRefused(
                f"no model credential is stored for {vendor!r}; the platform holds no authority "
                f"to call this vendor",
                reason_code="credential_unavailable",
            )

        secret = str((body.get("data") or {}).get(KEY_FIELD, "")).strip()
        if not secret:
            raise ResolutionRefused(
                f"the model credential record for {vendor!r} carries no {KEY_FIELD!r} value",
                reason_code="credential_unavailable",
            )

        # The version comes from KV v2's `metadata` — measured (analysis U2): the fabric's
        # `_kv_data` returns only the `data` dict, so the version is not "free" and is taken
        # explicitly here. Carrying it is what makes "which rotation generation authorised this
        # call" answerable, which is the difference between before-the-leak and after-the-rotation.
        version = (body.get("metadata") or {}).get("version", "?")
        return ModelCredential(
            secret=secret,
            reference=f"vault:{CREDENTIAL_PATH}/{vendor}@v{version}",
        )


__all__ = [
    "CREDENTIAL_PATH",
    "KEY_FIELD",
    "BrokeredModelCredential",
    "ModelCredential",
]
