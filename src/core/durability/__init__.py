# SPDX-License-Identifier: Apache-2.0
"""Durability seam (sealed core).

``resume`` is deliberately NOT re-exported here. It sits above this package — it needs
``RunState`` and the observation bracket — so importing it from the package __init__
would make every low-level durability import pull in the whole graph and cycle. Import
it directly: ``from core.durability.resume import resume_run``.
"""

from core.durability.credentials import (
    CredentialUnavailableError,
    DatabaseCredential,
    NomadWorkloadIdentity,
    VaultDatabaseCredentials,
)
from core.durability.lease import LeaseSupersededError, RunLease
from core.durability.memory import InMemoryDurabilityProvider
from core.durability.postgres import DurabilityStoreError, PostgresDurabilityProvider
from core.durability.types import (
    CheckpointBlob,
    DurabilityProvider,
    IntentRecord,
    ResultRecord,
    RunOutcome,
)

__all__ = [
    "CheckpointBlob",
    "CredentialUnavailableError",
    "DatabaseCredential",
    "DurabilityProvider",
    "DurabilityStoreError",
    "InMemoryDurabilityProvider",
    "IntentRecord",
    "LeaseSupersededError",
    "NomadWorkloadIdentity",
    "PostgresDurabilityProvider",
    "ResultRecord",
    "RunLease",
    "RunOutcome",
    "VaultDatabaseCredentials",
]
