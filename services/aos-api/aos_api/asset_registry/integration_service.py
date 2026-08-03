"""Transport-neutral M4 Integration Case application service."""

from __future__ import annotations

import json
import uuid
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import ValidationError

from aos_api.asset_registry.control_policy import (
    parse_strong_if_match,
    require_target_markings,
    strong_etag,
    validate_idempotency_key,
)
from aos_api.asset_registry.errors import (
    AssetNotFoundError,
    EvidenceIntegrityCorruptError,
    EvidenceReferenceInvalidError,
)
from aos_api.asset_registry.integration_contracts import (
    INTEGRATION_CASE_DETAIL_ADAPTER,
    INTEGRATION_EVIDENCE_ADAPTER,
    MAX_CASE_LIST_LIMIT,
    MAX_CASE_LIST_OFFSET,
    MAX_TIMELINE_ITEMS,
    CreateIntegrationCaseRequest,
    CreateIntegrationEvidenceSnapshotRequest,
    EvidenceOutcome,
    EvidenceType,
    IntegrationCaseDetail,
    IntegrationCaseListResponse,
    IntegrationCaseTimelineResponse,
    IntegrationEvidenceEnvelope,
    IntegrationEvidenceSnapshotResponse,
    IntegrationStage,
)
from aos_api.asset_registry.integration_policy import (
    CREATE_CASE_OPERATION,
    GET_CASE_OPERATION,
    LIST_CASES_OPERATION,
    LIST_TIMELINE_OPERATION,
    PROJECT_CASE_OPERATION,
    require_integration_case_role,
    require_integration_case_visibility,
    validate_integration_case_scope,
)
from aos_api.asset_registry.integration_stage_policy import (
    PlannedBasis,
    evaluate_contract_stage_policy,
)
from aos_api.asset_registry.integration_store import (
    IntegrationCommandReceipt,
    IntegrationCommandResult,
    PostgresIntegrationStore,
    ProjectionSnapshot,
    StoredIntegrationCase,
    _lock_case,
    _policy_documents,
)


@dataclass(frozen=True, slots=True)
class IntegrationRequestContext:
    """Verified identity context supplied by the transport boundary."""

    org_id: str
    project_id: str
    subject: str
    roles: tuple[str, ...]
    markings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TrustedProducerContext:
    """Server-owned capability granted to one internal Evidence producer."""

    org_id: str
    project_id: str
    producer: str
    markings: tuple[str, ...]
    evidence_types: tuple[EvidenceType, ...]


class IntegrationCaseReader(Protocol):
    def list_cases(
        self,
        *,
        org_id: str,
        project_id: str,
        scope: str,
        allowed_markings: Collection[str],
        limit: int,
        offset: int,
    ) -> IntegrationCaseListResponse: ...

    def get_case_detail(
        self,
        *,
        org_id: str,
        project_id: str,
        case_id: str,
        allowed_markings: Collection[str],
    ) -> IntegrationCaseDetail: ...

    def list_case_timeline(
        self,
        *,
        org_id: str,
        project_id: str,
        case_id: str,
        allowed_markings: Collection[str],
        limit: int,
        offset: int,
    ) -> IntegrationCaseTimelineResponse: ...


class IntegrationMarkingResolver(Protocol):
    def required_markings_for_create_in_transaction(
        self,
        conn: Any,
        *,
        org_id: str,
        project_id: str,
        installation_id: str,
        principal_markings: Collection[str],
    ) -> Sequence[str]: ...


class IntegrationExpiryProjector(Protocol):
    def refresh_case_if_due(
        self, *, org_id: str, project_id: str, case_id: str
    ) -> object: ...

    def project_expired_batch(
        self,
        *,
        org_id: str | None = None,
        project_id: str | None = None,
        batch_size: int = 100,
    ) -> object: ...


class EvidenceWriter(Protocol):
    def write(
        self, *, case_id: str, evidence: IntegrationEvidenceEnvelope
    ) -> ProjectionSnapshot: ...


class IntegrationCaseService:
    """Authorize and orchestrate the five frozen Integration Case use cases."""

    def __init__(
        self,
        *,
        store: PostgresIntegrationStore,
        reader: IntegrationCaseReader,
        marking_resolver: IntegrationMarkingResolver,
        expiry_projector: IntegrationExpiryProjector,
    ) -> None:
        self._store = store
        self._reader = reader
        self._marking_resolver = marking_resolver
        self._expiry_projector = expiry_projector

    def list_cases(
        self,
        *,
        context: IntegrationRequestContext,
        scope: str,
        limit: int = MAX_CASE_LIST_LIMIT,
        offset: int = 0,
    ) -> IntegrationCaseListResponse:
        context = _context(context)
        require_integration_case_role(
            roles=context.roles, operation=LIST_CASES_OPERATION
        )
        normalized_scope = validate_integration_case_scope(scope)
        limit, offset = _paging(limit, offset, maximum=MAX_CASE_LIST_LIMIT)
        if normalized_scope == "current":
            _refresh_current_scope(self._expiry_projector, context=context)
        return self._reader.list_cases(
            org_id=context.org_id,
            project_id=context.project_id,
            scope=normalized_scope,
            allowed_markings=context.markings,
            limit=limit,
            offset=offset,
        )

    def create_case(
        self,
        *,
        context: IntegrationRequestContext,
        request: CreateIntegrationCaseRequest,
        idempotency_key: str | None,
    ) -> IntegrationCommandReceipt:
        context = _context(context)
        request = CreateIntegrationCaseRequest.model_validate(request)
        require_integration_case_role(
            roles=context.roles, operation=CREATE_CASE_OPERATION
        )
        key = validate_idempotency_key(idempotency_key)
        body = request.model_dump(mode="json", by_alias=True, exclude_none=False)

        def handler(conn: Any) -> IntegrationCommandResult:
            required_markings = (
                self._marking_resolver.required_markings_for_create_in_transaction(
                    conn,
                    org_id=context.org_id,
                    project_id=context.project_id,
                    installation_id=request.installation_id,
                    principal_markings=context.markings,
                )
            )
            require_target_markings(
                principal_markings=context.markings,
                target_markings=required_markings,
            )
            stored = self._store.create_current_case_in_transaction(
                conn,
                org_id=context.org_id,
                project_id=context.project_id,
                request=request,
                owner=context.subject,
                required_markings=required_markings,
            )
            detail = _created_case_detail(stored)
            _require_current_detail(detail, case_id=stored.case_id)
            return IntegrationCommandResult(
                case_pk=stored.case_pk,
                status_code=201,
                response_json=detail.model_dump(
                    mode="json", by_alias=True, exclude_none=False
                ),
                response_etag=strong_etag(detail.etag_version),
            )

        receipt = self._store.execute_idempotent(
            org_id=context.org_id,
            project_id=context.project_id,
            operation=CREATE_CASE_OPERATION,
            idempotency_key=key,
            subject=context.subject,
            request_json=body,
            if_match_etag=None,
            handler=handler,
        )
        self._authorize_case_receipt(receipt, context=context, expected_case_id=None)
        return receipt

    def get_case(
        self,
        *,
        context: IntegrationRequestContext,
        case_id: str,
    ) -> IntegrationCaseDetail:
        context = _context(context)
        require_integration_case_role(roles=context.roles, operation=GET_CASE_OPERATION)
        case_id = _case_id(case_id)
        self._authorize_case(case_id=case_id, context=context)
        self._expiry_projector.refresh_case_if_due(
            org_id=context.org_id,
            project_id=context.project_id,
            case_id=case_id,
        )
        detail = self._reader.get_case_detail(
            org_id=context.org_id,
            project_id=context.project_id,
            case_id=case_id,
            allowed_markings=context.markings,
        )
        _require_detail_binding(detail, case_id=case_id)
        return detail

    def create_evidence_snapshot(
        self,
        *,
        context: IntegrationRequestContext,
        case_id: str,
        request: CreateIntegrationEvidenceSnapshotRequest,
        idempotency_key: str | None,
        if_match: str | None,
    ) -> IntegrationCommandReceipt:
        context = _context(context)
        case_id = _case_id(case_id)
        request = CreateIntegrationEvidenceSnapshotRequest.model_validate(request)
        require_integration_case_role(
            roles=context.roles, operation=PROJECT_CASE_OPERATION
        )
        key = validate_idempotency_key(idempotency_key)
        _, expected_version = parse_strong_if_match(if_match)
        body = request.model_dump(mode="json", by_alias=True, exclude_none=False)

        def handler(conn: Any) -> IntegrationCommandResult:
            locked = _lock_case_for_service(
                self._store,
                conn,
                org_id=context.org_id,
                project_id=context.project_id,
                case_id=case_id,
            )
            if locked["scope"] != "current":
                raise AssetNotFoundError()
            require_integration_case_visibility(
                principal_markings=context.markings,
                target_markings=locked["required_markings"],
            )
            snapshot = self._store.project_case_in_transaction(
                conn,
                org_id=context.org_id,
                project_id=context.project_id,
                case=locked,
                if_match_etag=expected_version,
                cause="projection_rebuilt",
            )
            response = snapshot.response
            if response.case_id != case_id:
                raise EvidenceIntegrityCorruptError()
            return IntegrationCommandResult(
                case_pk=locked["case_pk"],
                status_code=201,
                response_json=response.model_dump(
                    mode="json", by_alias=True, exclude_none=False
                ),
                response_etag=strong_etag(response.etag_version),
            )

        receipt = self._store.execute_idempotent(
            org_id=context.org_id,
            project_id=context.project_id,
            operation=PROJECT_CASE_OPERATION,
            idempotency_key=key,
            subject=context.subject,
            request_json={"caseId": case_id, "body": body},
            if_match_etag=expected_version,
            handler=handler,
        )
        self._authorize_snapshot_receipt(
            receipt, context=context, expected_case_id=case_id
        )
        return receipt

    def list_timeline(
        self,
        *,
        context: IntegrationRequestContext,
        case_id: str,
        limit: int = MAX_TIMELINE_ITEMS,
        offset: int = 0,
    ) -> IntegrationCaseTimelineResponse:
        context = _context(context)
        require_integration_case_role(
            roles=context.roles, operation=LIST_TIMELINE_OPERATION
        )
        case_id = _case_id(case_id)
        limit, offset = _paging(limit, offset, maximum=MAX_TIMELINE_ITEMS)
        self._authorize_case(case_id=case_id, context=context)
        self._expiry_projector.refresh_case_if_due(
            org_id=context.org_id,
            project_id=context.project_id,
            case_id=case_id,
        )
        result = self._reader.list_case_timeline(
            org_id=context.org_id,
            project_id=context.project_id,
            case_id=case_id,
            allowed_markings=context.markings,
            limit=limit,
            offset=offset,
        )
        if result.case_id != case_id:
            raise EvidenceIntegrityCorruptError()
        return result

    def _authorize_case(
        self, *, case_id: str, context: IntegrationRequestContext
    ) -> StoredIntegrationCase:
        stored = self._store.get_case(
            org_id=context.org_id,
            project_id=context.project_id,
            case_id=case_id,
        )
        require_integration_case_visibility(
            principal_markings=context.markings,
            target_markings=stored.required_markings,
        )
        return stored

    def _authorize_case_receipt(
        self,
        receipt: IntegrationCommandReceipt,
        *,
        context: IntegrationRequestContext,
        expected_case_id: str | None,
    ) -> None:
        try:
            detail = INTEGRATION_CASE_DETAIL_ADAPTER.validate_json(
                json.dumps(receipt.response_json, separators=(",", ":"))
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise EvidenceIntegrityCorruptError() from exc
        if expected_case_id is not None and detail.case_id != expected_case_id:
            raise EvidenceIntegrityCorruptError()
        _require_current_detail(detail, case_id=detail.case_id)
        if receipt.response_etag != strong_etag(detail.etag_version):
            raise EvidenceIntegrityCorruptError()
        self._authorize_case(case_id=detail.case_id, context=context)

    def _authorize_snapshot_receipt(
        self,
        receipt: IntegrationCommandReceipt,
        *,
        context: IntegrationRequestContext,
        expected_case_id: str,
    ) -> None:
        try:
            response = IntegrationEvidenceSnapshotResponse.model_validate_json(
                json.dumps(receipt.response_json, separators=(",", ":"))
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise EvidenceIntegrityCorruptError() from exc
        if response.case_id != expected_case_id or receipt.response_etag != strong_etag(
            response.etag_version
        ):
            raise EvidenceIntegrityCorruptError()
        self._authorize_case(case_id=expected_case_id, context=context)


class TrustedEvidenceWriter:
    """Internal-only writer bound to a pre-authorized producer capability."""

    def __init__(
        self,
        *,
        store: PostgresIntegrationStore,
        context: TrustedProducerContext,
    ) -> None:
        self._store = store
        self._context = _producer_context(context)

    def write(
        self, *, case_id: str, evidence: IntegrationEvidenceEnvelope
    ) -> ProjectionSnapshot:
        case_id = _case_id(case_id)
        item = INTEGRATION_EVIDENCE_ADAPTER.validate_python(evidence)
        if (
            item.producer != self._context.producer
            or item.evidence_type not in self._context.evidence_types
        ):
            raise EvidenceReferenceInvalidError()
        stored = self._store.get_case(
            org_id=self._context.org_id,
            project_id=self._context.project_id,
            case_id=case_id,
        )
        if stored.scope != "current":
            raise AssetNotFoundError()
        require_integration_case_visibility(
            principal_markings=self._context.markings,
            target_markings=stored.required_markings,
        )
        require_target_markings(
            principal_markings=self._context.markings,
            target_markings=item.required_markings,
        )
        return self._store.project_case(
            org_id=self._context.org_id,
            project_id=self._context.project_id,
            case_id=case_id,
            if_match_etag=stored.etag_version,
            evidence=(item,),
            cause=_evidence_cause(item.outcome),
        )


def _lock_case_for_service(
    store: Any,
    conn: Any,
    *,
    org_id: str,
    project_id: str,
    case_id: str,
) -> Any:
    method = getattr(store, "lock_case_in_transaction", None)
    if callable(method):
        return method(
            conn,
            org_id=org_id,
            project_id=project_id,
            case_id=case_id,
        )
    return _lock_case(conn, org_id, project_id, case_id)


def _context(value: IntegrationRequestContext) -> IntegrationRequestContext:
    if not isinstance(value, IntegrationRequestContext):
        raise TypeError("verified IntegrationRequestContext is required")
    _normalized_text(value.org_id, "org_id")
    _normalized_text(value.project_id, "project_id")
    _normalized_text(value.subject, "subject")
    _normalized_tuple(value.roles, "roles")
    _normalized_tuple(value.markings, "markings")
    return value


def _refresh_current_scope(
    projector: IntegrationExpiryProjector,
    *,
    context: IntegrationRequestContext,
) -> None:
    batch_size = MAX_CASE_LIST_LIMIT
    for _ in range(100):
        result = projector.project_expired_batch(
            org_id=context.org_id,
            project_id=context.project_id,
            batch_size=batch_size,
        )
        if tuple(getattr(result, "failures", ())):
            raise EvidenceIntegrityCorruptError()
        selected = getattr(result, "selected_count", None)
        if not isinstance(selected, int) or isinstance(selected, bool) or selected < 0:
            raise EvidenceIntegrityCorruptError()
        if selected < batch_size:
            return
    raise EvidenceIntegrityCorruptError()


def _producer_context(value: TrustedProducerContext) -> TrustedProducerContext:
    if not isinstance(value, TrustedProducerContext):
        raise TypeError("TrustedProducerContext is required")
    _normalized_text(value.org_id, "org_id")
    _normalized_text(value.project_id, "project_id")
    _normalized_text(value.producer, "producer")
    _normalized_tuple(value.markings, "markings")
    if not isinstance(value.evidence_types, tuple):
        raise TypeError("evidence_types must be an immutable tuple")
    types = value.evidence_types
    if (
        not types
        or len(types) != len(set(types))
        or any(not isinstance(item, EvidenceType) for item in types)
    ):
        raise ValueError("trusted producer requires canonical Evidence types")
    return value


def _paging(limit: int, offset: int, *, maximum: int) -> tuple[int, int]:
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= maximum
    ):
        raise ValueError("limit is outside the canonical range")
    if (
        isinstance(offset, bool)
        or not isinstance(offset, int)
        or not 0 <= offset <= MAX_CASE_LIST_OFFSET
    ):
        raise ValueError("offset is outside the canonical range")
    return limit, offset


def _case_id(value: str) -> str:
    try:
        parsed = uuid.UUID(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise AssetNotFoundError() from exc
    if str(parsed) != value:
        raise AssetNotFoundError()
    return value


def _normalized_text(value: str, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or not value.isprintable()
        or "\x00" in value
    ):
        raise ValueError(f"{label} must be normalized text")
    return value


def _normalized_tuple(values: tuple[str, ...], label: str) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise TypeError(f"{label} must be an immutable tuple")
    normalized = tuple(_normalized_text(value, label) for value in values)
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{label} must not contain duplicates")
    return normalized


def _require_detail_binding(detail: IntegrationCaseDetail, *, case_id: str) -> None:
    if detail.case_id != case_id:
        raise EvidenceIntegrityCorruptError()


def _require_current_detail(detail: IntegrationCaseDetail, *, case_id: str) -> None:
    _require_detail_binding(detail, case_id=case_id)
    if detail.scope != "current":
        raise EvidenceIntegrityCorruptError()


def _evidence_cause(outcome: EvidenceOutcome) -> str:
    if outcome == EvidenceOutcome.VALID:
        return "evidence_added"
    if outcome == EvidenceOutcome.INVALID:
        return "negative_observed"
    if outcome == EvidenceOutcome.REVOKED:
        return "evidence_revoked"
    raise EvidenceReferenceInvalidError()


def _created_case_detail(stored: StoredIntegrationCase) -> IntegrationCaseDetail:
    if (
        stored.scope != "current"
        or stored.installation_id is None
        or stored.installation_revision is None
        or stored.composition_id is None
        or stored.lock_revision is None
        or stored.lock_hash is None
        or stored.overlay_revision is None
        or stored.owner is None
        or stored.current_revision != 1
        or stored.etag_version != 1
        or stored.snapshot_revision != 1
        or stored.computed_stage != IntegrationStage.PLANNED
    ):
        raise EvidenceIntegrityCorruptError()
    policy = evaluate_contract_stage_policy(
        planned_basis=PlannedBasis(
            exact_instance_revision=True,
            active_installation_revision=True,
            composition_lock_valid=True,
            composition_hash_valid=True,
        ),
        evidence=[],
        cutoff_at=stored.created_at,
    )
    gates, blockers, _ = _policy_documents(
        stored.case_id, policy, stored.created_at, IntegrationStage.PLANNED
    )
    for blocker in blockers:
        blocker["firstObservedAt"] = stored.created_at
        blocker["updatedAt"] = stored.created_at
    metric = {
        "value": None,
        "measuredCaseCount": 0,
        "eligibleCaseCount": 1,
        "cutoffAt": stored.created_at,
    }
    payload = {
        "caseId": stored.case_id,
        "scope": "current",
        "displayName": stored.display_name,
        "owner": stored.owner,
        "installationId": stored.installation_id,
        "installationRevision": stored.installation_revision,
        "overlayRevision": stored.overlay_revision,
        "compositionId": stored.composition_id,
        "lockRevision": stored.lock_revision,
        "lockHash": stored.lock_hash,
        "computedStage": IntegrationStage.PLANNED.value,
        "snapshotRevision": 1,
        "cutoffAt": stored.created_at,
        "blockerCount": sum(item["status"] == "open" for item in blockers),
        "etagVersion": 1,
        "createdAt": stored.created_at,
        "updatedAt": stored.updated_at,
        "stageGates": gates,
        "latestEvidence": [],
        "blockers": blockers,
        "nextProjectionAt": None,
        "metrics": {
            "connectorCount": {**metric, "aggregation": "distinct_count"},
            "pipelineCount": {**metric, "aggregation": "distinct_count"},
            "datasetRowCount": {**metric, "aggregation": "sum"},
            "latencyMs": {**metric, "aggregation": "max"},
        },
    }
    try:
        return INTEGRATION_CASE_DETAIL_ADAPTER.validate_python(payload)
    except ValidationError as exc:
        raise EvidenceIntegrityCorruptError() from exc
