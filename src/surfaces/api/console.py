# SPDX-License-Identifier: Apache-2.0
"""The admin console's routes — read the posture, request a change (044).

**The console asks; the trust fabric decides.** Nothing here applies a governance change.
The route validates, submits through `authority_submit`, and renders which of three things
the fabric did — applied, awaiting approval, or refused. There is no code path by which it
could decide, which is what makes C8 a fact about the architecture rather than a discipline.

**Why the routes are here and not in the portal.** The portal is a thin client with one HTTP
door and no credential of its own (Principle II); it has no backend to put a route in. So the
console's operations are admin-gated API routes the portal consumes. The enforceable claims
are the role gate and MCP's asserted absence — "portal only" is a statement about the
supported client, not a mechanism (spec FR-021a, corrected at analyze).

**`admin` is disjoint** (research R6): it confers configuration authority and no audit
visibility, and neither `operator` nor `compliance-analyst` confers configuration authority.
`test_admin_role_is_disjoint.py` asserts both directions, including that this module names no
other role — which is why the check below is written against one constant.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from core.audit.schema import AuditEventType
from core.authority.ask_binding import parse_ask_binding_record
from core.authority.endorsed_sources import SOURCE_FIELDS, validate_source_name
from core.authority.errors import ResolutionRefused
from core.authority.matrix import parse_matrix_record
from surfaces.api.authority_submit import (
    CONSOLE_RECORDS,
    AuthorityChangeRefused,
    AuthoritySubmitUnavailable,
    ConfigChange,
    RecordMoved,
)
from surfaces.api.dependencies import AuditDep, SubjectDep

#: The one role that may reach this surface. A second name here would be the widening
#: `ROLE_VISIBILITY` cannot see, which is why a row scans this module for the other two.
ADMIN_ROLE = "admin"

#: Where the connections record lives. Read by this surface and by nothing else yet — the
#: console labels it as such rather than implying a consumer it does not have (FR-022).
CONNECTIONS_PATH = "harness-authority/data/product-connections"

#: The ask binding, read WITH its metadata. `AskAuthority.read_binding_record` unwraps to the
#: secret alone, which loses the version a CAS guard needs and the `set_by` provenance carries.
ASK_BINDING_PATH = "harness-authority/data/ask-bindings"

#: What a connection record may contain. **Locations only** — there is no field here a
#: credential could be written into, which is FR-018b enforced by vocabulary rather than by
#: a filter somebody has to remember to apply.
CONNECTION_FIELDS: dict[str, frozenset[str]] = {
    "tfe": frozenset({"address", "organization", "workspace"}),
    "vault": frozenset({"address", "namespace"}),
}

#: How long the reachability probe waits. Short, because a person is watching a page — and
#: a slow product must not make the console look broken.
PROBE_TIMEOUT_SECONDS = 5.0


class ConfigUnavailable(Exception):
    """A record could not be read. **Not an empty record.**

    An unreadable fabric and a permissive configuration arrive identically — as no data — and
    treating either as the other would show an administrator a posture the platform does not
    have. `ProtectedSet` and `MatrixSource` both draw this line; this is the same one at the
    display layer, where the consequence is somebody deciding not to act.
    """


@dataclass(frozen=True)
class ConsoleConfig:
    """Where the console reads from. Callables in, nothing constructed here.

    The same shape `AskAuthority` takes and for the same reason: assembly supplies the trust
    fabric, tests supply dictionaries, and neither this module nor its rows know which.
    """

    #: The matrix, which `AskAuthority` already exposes unwrapped — a resolver wants the
    #: cells, not their metadata.
    read_matrix: Any
    #: Every OTHER record, **with its KV metadata**. The console needs the version for a CAS
    #: guard and `set_by` for provenance, and both live in metadata that an unwrapping reader
    #: discards. One reader for all of them, so no record's provenance depends on which
    #: accessor happened to be used.
    read_versioned: Any
    #: Whether a quorum is configured. Decides whether an applied change is *approved* or
    #: merely *ungated* — FR-007's disclosure, and the difference between a development
    #: posture and a production one.
    quorum_configured: bool = False


def _kv_body(record: Any) -> dict[str, Any]:
    """KV v2 nests data one level down; a raw mapping is already the body."""
    if not isinstance(record, dict):
        return {}
    data = record.get("data", record)
    inner = data.get("data", data) if isinstance(data, dict) else {}
    return inner if isinstance(inner, dict) else {}


def _version_of(record: Any) -> int | None:
    """The KV version, for the CAS guard a change will carry (US5).

    Read here rather than at write time so the guard describes **what the administrator
    actually saw**. Re-reading at submit would guard against nothing: it would fetch whatever
    is current and agree with it.
    """
    if not isinstance(record, dict):
        return None
    metadata = (
        (record.get("data") or {}).get("metadata") if isinstance(record.get("data"), dict) else None
    )
    version = (metadata or {}).get("version") if isinstance(metadata, dict) else None
    return int(version) if isinstance(version, int) else None


def read_configuration(config: ConsoleConfig) -> dict[str, Any]:
    """The platform's governance posture, assembled per request (US1, FR-001/002).

    **Every record is read fresh.** A cached posture is one that disagrees with the estate
    exactly when somebody is deciding whether to change it.

    Each record renders `unavailable` on its own rather than failing the page: an operator
    whose connections record is missing still needs to see which model answers, and a single
    unreadable record taking the whole console down would make a small gap look like an outage.
    """
    posture: dict[str, Any] = {}

    try:
        # **`read_versioned`, not `read_binding`** — and this was a real defect, not a
        # preference. `read_ask_binding` UNWRAPS the KV record to the secret alone, which is
        # right for a resolver that wants a binding and wrong here: it discards the metadata,
        # so the version would always have been `None` and the CAS guard would have guarded
        # nothing. `read_versioned` exists for exactly this distinction — 027 added it because
        # a credential's rotation generation is the fact the trail carries — and provenance is
        # the same shape of fact one record over.
        binding_record = config.read_versioned(ASK_BINDING_PATH)
        binding = parse_ask_binding_record(_kv_body(binding_record))
        posture["bindings"] = {
            "guidance_cell": binding.guidance_cell,
            "estate_cell": binding.estate_cell,
            "relevance_cell": binding.relevance_cell,
            "relevance_enabled": binding.relevance_enabled,
            "version": _version_of(binding_record),
            # WHO WROTE IT LAST (FR-019/US5), read from the record itself.
            #
            # The console stamps `set_by` on every change; a record written by an estate apply
            # carries none. So "last set by" needs no second store to consult — and no second
            # store means no two answers that disagree exactly when somebody needs to know
            # which writer won. An estate apply overwriting a console change is visible as a
            # version bump with the field gone.
            "set_by": _kv_body(binding_record).get("set_by", "") or "an estate apply",
        }
    except Exception:  # noqa: BLE001 — any read fault renders unavailable, never empty
        posture["bindings"] = {"unavailable": True}

    try:
        cells = parse_matrix_record(config.read_matrix())
        # Read-only context: what a binding MAY name. The console offers nothing outside it,
        # and refuses anything outside it at submit (FR-009, both sides).
        posture["qualified_cells"] = sorted(
            reference for reference, cell in cells.items() if not cell.withdrawn
        )
    except Exception:  # noqa: BLE001 — same reason
        posture["qualified_cells"] = {"unavailable": True}

    try:
        record = config.read_versioned(CONNECTIONS_PATH)
        body = _kv_body(record)
        posture["connections"] = {
            "products": {k: v for k, v in body.items() if k in CONNECTION_FIELDS},
            "version": _version_of(record),
            "set_by": body.get("set_by", "") or "an estate apply",
            # FR-022's honest middle: the record exists and nothing consumes it yet. Saying
            # so beats both silence and implying a consumer that does not exist.
            "consumed_by": "not yet consumed by dispatched runs",
        }
    except Exception:  # noqa: BLE001 — same reason
        posture["connections"] = {"unavailable": True}

    # FR-007/023b. An ungated estate is a legitimate development posture; an interface that
    # looks the same in both is not.
    posture["gating"] = "gated" if config.quorum_configured else "ungated"
    return posture


def probe_connection(product: str, address: str) -> str:
    """Whether the product answers at all — `verified`, `unreachable`, or `unverified`.

    **Any HTTP answer means reachable.** TFE's API answers 401 without a token, and 401 proves
    the endpoint is there; a probe treating non-2xx as down would report every correctly
    secured product as unreachable. Only a connection failure or a timeout is `unreachable`.

    Kept separate from the change outcome (FR-018c): a connection can be perfectly
    well-governed and simply wrong, which is the failure mode a binding does not have.
    """
    if not address.strip():
        return "unverified"
    endpoint = {
        "tfe": f"{address.rstrip('/')}/api/v2/ping",
        "vault": f"{address.rstrip('/')}/v1/sys/seal-status",
    }.get(product)
    if endpoint is None:
        return "unverified"
    try:
        request = urllib.request.Request(endpoint, method="GET")  # noqa: S310
        with urllib.request.urlopen(request, timeout=PROBE_TIMEOUT_SECONDS):  # noqa: S310
            return "verified"
    except urllib.error.HTTPError:
        # It answered. A 401 or 403 is the product telling us it is there and we are not
        # authenticated — which is exactly right, since the console holds no credential.
        return "verified"
    except Exception:  # noqa: BLE001 — anything else is not an answer
        return "unreachable"


def _validate_payload(body: Any, config: ConsoleConfig) -> None:
    """Refuse a change the platform would refuse anyway, before the fabric is asked.

    **Two checks, and both are about not offering what cannot be accepted.**

    A binding may name only a cell the Qualified Model Matrix carries — otherwise an
    administrator is invited to choose something that will be refused, which reads as the
    platform being broken rather than as governance working. `unqualified_cell` is the
    matrix's own word, reused so the trail says the same thing at both ends.

    A connection may carry only *locations*. The vocabulary has no field a credential could
    be written into (FR-018b), so this is a closed set rather than a filter over a
    credential-shaped one — a filter is something a future field slips past.
    """
    # THE RECORD NAME, checked at the route as well as in the submitter (defence in depth).
    # `ConfigChange.path_within` refuses anything outside the closed set — but only when it is
    # called, which makes the refusal a property of the submitter that happens to be wired.
    # The route refuses regardless, so scoping does not depend on assembly.
    if body.record not in CONSOLE_RECORDS:
        raise ValueError(
            f"{body.record!r} is not a record the console may change. The writable set is "
            f"{sorted(CONSOLE_RECORDS)}; ceilings, the model matrix and the protected set are "
            f"estate governance this feature deliberately left in Terraform."
        )

    if body.record == "ask-bindings":
        cells = _qualified_cells(config)
        for field in ("guidance_cell", "estate_cell", "relevance_cell"):
            reference = str(body.payload.get(field, "")).strip()
            if reference and cells is not None and reference not in cells:
                raise ValueError(
                    f"{reference!r} is not a qualified cell. A binding may name only what the "
                    f"Qualified Model Matrix carries — promotion is an eval-gated act "
                    f"(Principle VIII), not something an interface can grant."
                )
    if body.record == "product-connections":
        for product, fields in body.payload.items():
            if product == "set_by":
                continue
            permitted = CONNECTION_FIELDS.get(product)
            if permitted is None:
                raise ValueError(
                    f"{product!r} is not a product this console configures; the set is "
                    f"{sorted(CONNECTION_FIELDS)}"
                )
            if not isinstance(fields, dict):
                raise ValueError(f"{product!r} must carry named location fields")
            unknown = sorted(set(fields) - permitted)
            if unknown:
                raise ValueError(
                    f"{unknown} are not location fields for {product!r}. Connections name "
                    f"WHERE a product is; the material used to authenticate to it lives in "
                    f"the trust store and is never entered here."
                )
    if body.record == "endorsed-sources":
        _validate_endorsed_sources(body.payload)


def _validate_endorsed_sources(payload: Mapping[str, Any]) -> None:
    """The fourth record's shape, refused at the route for the other three's reasons (045).

    Endorsing is the act that makes somebody's documents citable, so what an administrator may
    put in the record is a closed set for the same reason a connection's is: there must be no
    field a credential could be written into. A private source's material is trust-store
    material referenced per sync (FR-018b's posture, unchanged).

    The **name** is checked here as well as in the parser because it is the citation namespace
    — a name carrying a separator would let one source's documents resolve inside another's,
    and being told that at the point of typing is the difference between governance working
    and the platform looking broken.
    """
    for name, entry in payload.items():
        if name in {"set_by", "schema_version"}:
            continue
        try:
            validate_source_name(name)
        except ResolutionRefused as refused:
            raise ValueError(str(refused)) from refused
        if not isinstance(entry, Mapping):
            raise ValueError(f"endorsed source {name!r} must carry named fields")
        unknown = sorted(set(entry) - SOURCE_FIELDS)
        if unknown:
            raise ValueError(
                f"{unknown} are not fields of an endorsed source. An endorsement names WHERE "
                f"the material is, WHO trusted it and WHICH version answers rest on; the "
                f"material used to reach a private source lives in the trust store and is "
                f"never entered here."
            )
        if str(entry.get("location", "")).strip() and not str(entry.get("endorsed_by", "")).strip():
            raise ValueError(
                f"endorsed source {name!r} names a location and no endorser. The endorsement "
                f"IS the trust statement the citation gate rests on (FR-002); a source with "
                f"no named endorser is content that arrived, not content somebody vouched for."
            )


def _qualified_cells(config: ConsoleConfig) -> frozenset[str] | None:
    """What a binding may name, or `None` when the matrix cannot be read.

    `None` rather than an empty set, and the caller skips the check: an unreadable matrix must
    not refuse every binding as unqualified. That would present a fabric outage as an estate
    of misconfigured cells — the exact confusion `read_matrix`'s own docstring names.
    """
    try:
        cells = parse_matrix_record(config.read_matrix())
    except Exception:  # noqa: BLE001 — unreadable is not empty
        return None
    return frozenset(reference for reference, cell in cells.items() if not cell.withdrawn)


def require_admin(subject: Any, audit: Any = None) -> None:
    """Refuse anyone without the console's role, **and record the attempt**.

    The check the whole surface rests on. Recording is not decoration: 022 established that a
    refusal records for the same reason an approval does — a boundary a caller can probe
    without trace is not a boundary, and repeated attempts against an administrative surface
    are exactly the shape a trail should show rather than swallow.

    `audit` is optional so the function stays callable from a row that is only testing the
    check; every route passes one.
    """
    if ADMIN_ROLE in getattr(subject, "roles", frozenset()):
        return
    if audit is not None:
        _record_console_event(
            audit,
            subject,
            event=AuditEventType.AUTHORITY_REFUSED,
            payload={"reason_code": "not_an_admin", "surface": "console"},
        )
    raise HTTPException(
        status.HTTP_403_FORBIDDEN,
        "the console is administrative; this subject does not hold that role",
    )


def _record_console_event(
    audit: Any, subject: Any, *, event: AuditEventType, payload: dict[str, Any]
) -> None:
    """Reads and changes are both recorded. Evidence access is itself audited (Principle IX),
    and configuration is evidence of what the platform will do."""
    audit.append_event(
        correlation_id=f"console-{subject.subject_user_id}",
        tenant_id=subject.tenant_id,
        event_type=event,
        payload={"actor": subject.subject_user_id, **payload},
    )


class ChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record: str = Field(description="Which governance record to change")
    payload: dict[str, Any] = Field(default_factory=dict)
    cas: int | None = None
    key: str = ""


def build_router(*, config: ConsoleConfig, submitter: Any) -> APIRouter:
    """The console's routes. Both require `admin`; neither decides anything."""
    router = APIRouter(tags=["console"], prefix="/console")

    @router.get("/configuration")
    def read_console_configuration(subject: SubjectDep, audit: AuditDep) -> dict[str, Any]:
        require_admin(subject, audit)
        posture = read_configuration(config)
        _record_console_event(
            audit,
            subject,
            event=AuditEventType.RECORD_READ,
            payload={"records": sorted(posture), "surface": "console"},
        )
        return posture

    @router.post("/connections/verify")
    def verify_connection(subject: SubjectDep, audit: AuditDep) -> dict[str, Any]:
        """Ask each configured product whether it is there. **A separate act** (FR-018c).

        Verification is not part of a change's outcome and must never be folded into one: a
        connection can be perfectly well-governed and simply wrong, which is the failure mode
        a binding does not have. "The fabric accepted it" and "the product answered" are two
        facts, and an interface that reports the first as the second has told the
        administrator the opposite of what happened.
        """
        require_admin(subject, audit)
        posture = read_configuration(config)
        connections = posture.get("connections") or {}
        products = connections.get("products") or {} if isinstance(connections, dict) else {}

        results = {
            product: probe_connection(product, str((fields or {}).get("address", "")))
            for product, fields in products.items()
        }
        _record_console_event(
            audit,
            subject,
            event=AuditEventType.RECORD_READ,
            payload={"surface": "console", "records": ["connection-verification"]},
        )
        return {"verification": results}

    @router.post("/changes")
    def request_change(body: ChangeRequest, subject: SubjectDep, audit: AuditDep) -> Any:
        require_admin(subject, audit)

        # SELF-GRANT, refused here and nowhere else it could be (FR-017). An administrator
        # who can widen their own role has not been granted authority — they have taken it.
        if body.record == "claim-mappings" and body.payload.get("role") == ADMIN_ROLE:
            claim_value = str(body.payload.get("claim_value", ""))
            if claim_value and claim_value == subject.subject_user_id:
                _record_console_event(
                    audit,
                    subject,
                    event=AuditEventType.AUTHORITY_REFUSED,
                    payload={"reason_code": "self_grant_refused", "record": body.record},
                )
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "an administrator may not grant themselves the admin role; ask another "
                    "administrator, which is what makes the role a grant rather than a claim",
                )

        # VALIDATION BEFORE THE FABRIC IS ASKED (C1, FR-009). A change the platform would
        # refuse anyway must not reach Vault: a rejected write still costs a round trip, a
        # log line, and — where a quorum is configured — an approver's attention on a request
        # that was never going to be applied.
        try:
            _validate_payload(body, config)
        except ValueError as invalid:
            _record_console_event(
                audit,
                subject,
                event=AuditEventType.AUTHORITY_REFUSED,
                payload={"reason_code": "invalid_change", "record": body.record},
            )
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(invalid)) from invalid

        change = ConfigChange(
            record=body.record,
            payload=dict(body.payload),
            requester=subject.subject_user_id,
            cas=body.cas,
            key=body.key,
        )

        try:
            outcome = submitter.submit_change(change)
        except RecordMoved as moved:
            _record_console_event(
                audit,
                subject,
                event=AuditEventType.AUTHORITY_REFUSED,
                payload={"reason_code": "record_moved", "record": body.record},
            )
            raise HTTPException(status.HTTP_409_CONFLICT, str(moved)) from moved
        except AuthorityChangeRefused as refused:
            _record_console_event(
                audit,
                subject,
                event=AuditEventType.AUTHORITY_DENIED,
                payload={"reason_code": "authority_change_denied", "record": body.record},
            )
            raise HTTPException(status.HTTP_403_FORBIDDEN, str(refused)) from refused
        except AuthoritySubmitUnavailable as down:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(down)) from down

        _record_console_event(
            audit,
            subject,
            event=AuditEventType.AUTHORITY_CHANGE_OBSERVED,
            payload={"record": body.record, "outcome": outcome.state},
        )

        if outcome.is_pending:
            # 202, never 403. 007's seam already names the trap: a client reading 403 stops
            # asking, so a change approved twenty minutes later is never collected and the
            # requester concludes it was refused when it was in fact granted.
            return _json(
                status.HTTP_202_ACCEPTED,
                {
                    "state": "pending",
                    "accessor": outcome.accessor,
                    "expires_at": outcome.expires_at,
                    "message": "awaiting approval; this change is NOT in force",
                },
            )

        return _json(
            status.HTTP_200_OK,
            {
                "state": "applied",
                # FR-007. An ungated estate is legitimate and must not read as an approval
                # that happened.
                "gating": "gated" if config.quorum_configured else "ungated",
                "message": (
                    "applied"
                    if config.quorum_configured
                    else "applied WITHOUT approval — no quorum is configured in this estate"
                ),
            },
        )

    return router


def _json(code: int, body: dict[str, Any]) -> JSONResponse:
    return JSONResponse(status_code=code, content=body)


__all__ = [
    "ADMIN_ROLE",
    "CONNECTION_FIELDS",
    "CONNECTIONS_PATH",
    "ConfigUnavailable",
    "ConsoleConfig",
    "build_router",
    "probe_connection",
    "read_configuration",
    "require_admin",
]
