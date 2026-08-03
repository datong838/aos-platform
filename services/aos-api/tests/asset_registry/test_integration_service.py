"""Application-service tests for the five M4 Integration Case use cases."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.errors import (
    AssetNotFoundError,
    DutySeparationRequiredError,
    EvidenceReferenceInvalidError,
    IdempotencyConflictError,
    RevisionConflictError,
)
from aos_api.asset_registry.integration_contracts import (
    CreateIntegrationCaseRequest,
    CreateIntegrationEvidenceSnapshotRequest,
    CurrentIntegrationCaseDetail,
    EvidenceType,
    IntegrationCaseListResponse,
    IntegrationCaseTimelineResponse,
    IntegrationEvidenceSnapshotResponse,
    IntegrationStage,
    SourceConnectionEvidence,
)
from aos_api.asset_registry.integration_service import (
    IntegrationCaseService,
    IntegrationRequestContext,
    TrustedEvidenceWriter,
    TrustedProducerContext,
)
from aos_api.asset_registry.integration_store import (
    IntegrationCommandReceipt,
    IntegrationCommandResult,
    ProjectionMetrics,
    ProjectionSnapshot,
    StoredIntegrationCase,
)

NOW = datetime(2026, 8, 4, 9, 0, tzinfo=UTC)
CASE_ID = "64000000-0000-4000-8000-000000000001"
CASE_PK = uuid.UUID("64000000-0000-4000-8000-000000000002")
INSTANCE_PK = uuid.UUID("64000000-0000-4000-8000-000000000003")
INSTALLATION_ID = "65000000-0000-4000-8000-000000000001"
ZERO_HASH = "sha256:" + "0" * 64
STAGES = (
    "planned",
    "connection_verified",
    "data_verified",
    "ontology_verified",
    "logic_verified",
    "workshop_verified",
    "production_ready",
    "production_active",
)


def _gates() -> list[dict[str, object]]:
    return [
        {
            "stage": stage,
            "status": "satisfied"
            if index == 0
            else ("blocked" if index == 1 else "not_evaluated"),
            "evidenceRefs": [],
            "reasonRefs": [],
        }
        for index, stage in enumerate(STAGES)
    ]


def _metric(aggregation: str) -> dict[str, object]:
    return {
        "value": None,
        "aggregation": aggregation,
        "measuredCaseCount": 0,
        "eligibleCaseCount": 1,
        "cutoffAt": NOW,
    }


def _detail(*, etag: int = 1) -> CurrentIntegrationCaseDetail:
    return CurrentIntegrationCaseDetail.model_validate(
        {
            "caseId": CASE_ID,
            "scope": "current",
            "displayName": "微信小店接入",
            "owner": "owner:test",
            "installationId": INSTALLATION_ID,
            "installationRevision": 1,
            "overlayRevision": "overlay-v1",
            "compositionId": "65000000-0000-4000-8000-000000000002",
            "lockRevision": 1,
            "lockHash": ZERO_HASH,
            "computedStage": "planned",
            "snapshotRevision": etag,
            "cutoffAt": NOW,
            "blockerCount": 0,
            "etagVersion": etag,
            "createdAt": NOW,
            "updatedAt": NOW,
            "stageGates": _gates(),
            "latestEvidence": [],
            "blockers": [],
            "nextProjectionAt": None,
            "metrics": {
                "connectorCount": _metric("distinct_count"),
                "pipelineCount": _metric("distinct_count"),
                "datasetRowCount": _metric("sum"),
                "latencyMs": _metric("max"),
            },
        }
    )


def _stored(*, etag: int = 1) -> StoredIntegrationCase:
    return StoredIntegrationCase(
        org_id="org",
        project_id="project",
        case_pk=CASE_PK,
        case_id=CASE_ID,
        instance_pk=INSTANCE_PK,
        scope="current",
        display_name="微信小店接入",
        owner="owner:test",
        required_markings=("internal",),
        current_revision=etag,
        etag_version=etag,
        installation_pk=uuid.uuid4(),
        installation_id=INSTALLATION_ID,
        installation_revision=1,
        composition_pk=uuid.uuid4(),
        composition_id="65000000-0000-4000-8000-000000000002",
        lock_revision=1,
        lock_hash=ZERO_HASH,
        overlay_revision="overlay-v1",
        snapshot_revision=etag,
        computed_stage=IntegrationStage.PLANNED,
        created_at=NOW,
        updated_at=NOW,
    )


def _snapshot(*, etag: int = 2) -> ProjectionSnapshot:
    response = IntegrationEvidenceSnapshotResponse.model_validate(
        {
            "caseId": CASE_ID,
            "snapshotRevision": etag,
            "instanceRevision": etag,
            "cutoffAt": NOW,
            "computedStage": "planned",
            "stagePolicyVersion": "aos.integration-stage/v1",
            "snapshotHash": ZERO_HASH,
            "nextProjectionAt": None,
            "evidenceCount": 0,
            "stageGates": _gates(),
            "blockerRefs": [],
            "etagVersion": etag,
            "createdAt": NOW,
        }
    )
    return ProjectionSnapshot(
        response=response,
        stage_event=None,
        metrics=ProjectionMetrics(None, None, None, None),
    )


class FakeStore:
    def __init__(self) -> None:
        self.case = _stored()
        self.receipts: dict[
            tuple[str, str], tuple[object, IntegrationCommandReceipt]
        ] = {}
        self.create_count = 0
        self.project_count = 0
        self.writer_calls: list[tuple[object, str]] = []

    def execute_idempotent(self, **kwargs: Any) -> IntegrationCommandReceipt:
        key = (kwargs["operation"], kwargs["idempotency_key"])
        signature = (
            kwargs["subject"],
            kwargs["request_json"],
            kwargs["if_match_etag"],
        )
        existing = self.receipts.get(key)
        if existing is not None:
            if existing[0] != signature:
                raise IdempotencyConflictError("idempotency key was reused")
            receipt = existing[1]
            return IntegrationCommandReceipt(
                case_pk=receipt.case_pk,
                status_code=receipt.status_code,
                response_json=receipt.response_json,
                response_etag=receipt.response_etag,
                replayed=True,
            )
        result: IntegrationCommandResult = kwargs["handler"](object())
        receipt = IntegrationCommandReceipt(
            case_pk=result.case_pk,
            status_code=result.status_code,
            response_json=result.response_json,
            response_etag=result.response_etag,
            replayed=False,
        )
        self.receipts[key] = (signature, receipt)
        return receipt

    def create_current_case_in_transaction(self, _conn: Any, **_kwargs: Any):
        self.create_count += 1
        self.case = _stored(etag=1)
        return self.case

    def lock_case_in_transaction(self, _conn: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "case_pk": self.case.case_pk,
            "case_id": uuid.UUID(self.case.case_id),
            "scope": self.case.scope,
            "required_markings": list(self.case.required_markings),
            "instance_pk": self.case.instance_pk,
            "current_revision": self.case.current_revision,
            "etag_version": self.case.etag_version,
        }

    def project_case_in_transaction(
        self, _conn: Any, *, if_match_etag: int, **_kwargs: Any
    ) -> ProjectionSnapshot:
        if if_match_etag != self.case.etag_version:
            raise RevisionConflictError("integration case ETag is stale")
        self.project_count += 1
        self.case = _stored(etag=if_match_etag + 1)
        return _snapshot(etag=if_match_etag + 1)

    def get_case(self, *, org_id: str, project_id: str, case_id: str):
        if (
            org_id != self.case.org_id
            or project_id != self.case.project_id
            or case_id != self.case.case_id
        ):
            raise AssetNotFoundError()
        return self.case

    def project_case(self, *, evidence: tuple[object, ...], cause: str, **kwargs: Any):
        if kwargs["if_match_etag"] != self.case.etag_version:
            raise RevisionConflictError()
        self.writer_calls.append((evidence[0], cause))
        self.case = _stored(etag=self.case.etag_version + 1)
        return _snapshot(etag=self.case.etag_version)


class FakeReader:
    def __init__(self, store: FakeStore) -> None:
        self.store = store
        self.list_markings: tuple[str, ...] = ()

    def list_cases(self, **kwargs: Any) -> IntegrationCaseListResponse:
        self.list_markings = tuple(kwargs["allowed_markings"])
        detail = _detail(etag=self.store.case.etag_version)
        item = {
            key: value
            for key, value in detail.model_dump(
                mode="python", by_alias=True, exclude_none=False
            ).items()
            if key
            in {
                "caseId",
                "scope",
                "displayName",
                "owner",
                "installationId",
                "overlayRevision",
                "computedStage",
                "snapshotRevision",
                "cutoffAt",
                "blockerCount",
                "etagVersion",
                "createdAt",
                "updatedAt",
            }
        }
        stats = {
            "caseCount": {**_metric("count"), "value": 1, "measuredCaseCount": 1},
            "productionActiveCount": {
                **_metric("count"),
                "value": 0,
                "measuredCaseCount": 1,
            },
            "connectorCount": _metric("distinct_count"),
            "pipelineCount": _metric("distinct_count"),
            "datasetRowCount": _metric("sum"),
            "latencyMs": _metric("max"),
        }
        return IntegrationCaseListResponse.model_validate(
            {
                "items": [item],
                "scope": kwargs["scope"],
                "total": 1,
                "limit": kwargs["limit"],
                "offset": kwargs["offset"],
                "stats": stats,
            }
        )

    def get_case_detail(self, **_kwargs: Any):
        return _detail(etag=self.store.case.etag_version)

    def get_case_detail_in_transaction(self, _conn: Any, **_kwargs: Any):
        return _detail(etag=self.store.case.etag_version)

    def list_case_timeline(self, **kwargs: Any) -> IntegrationCaseTimelineResponse:
        return IntegrationCaseTimelineResponse.model_validate(
            {
                "caseId": CASE_ID,
                "scope": "current",
                "items": [
                    {
                        "sequence": 1,
                        "snapshotRevision": 1,
                        "oldStage": None,
                        "newStage": "planned",
                        "cause": "created",
                        "reasonRefs": [],
                        "createdAt": NOW,
                    }
                ],
                "total": 1,
                "limit": kwargs["limit"],
                "offset": kwargs["offset"],
            }
        )


class FakeMarkingResolver:
    def required_markings_for_create_in_transaction(self, _conn: Any, **_kwargs: Any):
        return ("internal",)


class FakeExpiryProjector:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def refresh_case_if_due(self, **kwargs: Any) -> bool:
        self.calls.append(kwargs["case_id"])
        return False


def _context(*, roles: tuple[str, ...], markings: tuple[str, ...] = ("internal",)):
    return IntegrationRequestContext(
        org_id="org",
        project_id="project",
        subject="owner:test",
        roles=roles,
        markings=markings,
    )


def _request() -> CreateIntegrationCaseRequest:
    return CreateIntegrationCaseRequest.model_validate(
        {
            "installationId": INSTALLATION_ID,
            "overlayRevision": "overlay-v1",
            "displayName": "微信小店接入",
        }
    )


def _service(store: FakeStore):
    reader = FakeReader(store)
    expiry = FakeExpiryProjector()
    return (
        IntegrationCaseService(
            store=store,  # type: ignore[arg-type]
            reader=reader,
            marking_resolver=FakeMarkingResolver(),
            expiry_projector=expiry,
        ),
        reader,
        expiry,
    )


def test_five_use_cases_roles_markings_and_expiry_refresh() -> None:
    store = FakeStore()
    service, reader, expiry = _service(store)
    maker = _context(roles=("integration-case-maker",))
    created = service.create_case(
        context=maker, request=_request(), idempotency_key="create-1"
    )
    assert created.status_code == 201

    reader_context = _context(roles=("integration-case-reader",))
    listed = service.list_cases(
        context=reader_context, scope="current", limit=20, offset=0
    )
    assert listed.total == 1 and reader.list_markings == ("internal",)
    assert service.get_case(context=reader_context, case_id=CASE_ID).case_id == CASE_ID
    timeline = service.list_timeline(
        context=reader_context, case_id=CASE_ID, limit=10, offset=0
    )
    assert timeline.items[0].cause == "created"

    projector = _context(roles=("integration-case-projector",))
    snapshot = service.create_evidence_snapshot(
        context=projector,
        case_id=CASE_ID,
        request=CreateIntegrationEvidenceSnapshotRequest(),
        idempotency_key="project-1",
        if_match='"1"',
    )
    assert snapshot.response_etag == '"2"'
    assert expiry.calls == [CASE_ID, CASE_ID]

    with pytest.raises(AssetNotFoundError):
        service.get_case(
            context=_context(
                roles=("admin",),
                markings=(),
            ),
            case_id=CASE_ID,
        )
    with pytest.raises(DutySeparationRequiredError):
        service.create_case(
            context=reader_context, request=_request(), idempotency_key="denied"
        )


def test_receipt_first_replay_restart_conflict_and_cas() -> None:
    store = FakeStore()
    service, _, _ = _service(store)
    maker = _context(roles=("integration-case-maker",))
    first = service.create_case(
        context=maker, request=_request(), idempotency_key="create-1"
    )
    restarted, _, _ = _service(store)
    replay = restarted.create_case(
        context=maker, request=_request(), idempotency_key="create-1"
    )
    assert not first.replayed and replay.replayed and store.create_count == 1
    changed = _request().model_copy(update={"display_name": "另一个案例"})
    with pytest.raises(IdempotencyConflictError):
        restarted.create_case(
            context=maker, request=changed, idempotency_key="create-1"
        )

    projector = _context(roles=("integration-case-projector",))
    first_projection = restarted.create_evidence_snapshot(
        context=projector,
        case_id=CASE_ID,
        request=CreateIntegrationEvidenceSnapshotRequest(),
        idempotency_key="project-1",
        if_match='"1"',
    )
    replay_projection = restarted.create_evidence_snapshot(
        context=projector,
        case_id=CASE_ID,
        request=CreateIntegrationEvidenceSnapshotRequest(),
        idempotency_key="project-1",
        if_match='"1"',
    )
    assert not first_projection.replayed and replay_projection.replayed
    assert store.project_count == 1
    with pytest.raises(IdempotencyConflictError):
        restarted.create_evidence_snapshot(
            context=projector,
            case_id=CASE_ID,
            request=CreateIntegrationEvidenceSnapshotRequest(),
            idempotency_key="project-1",
            if_match='"2"',
        )
    with pytest.raises(RevisionConflictError):
        restarted.create_evidence_snapshot(
            context=projector,
            case_id=CASE_ID,
            request=CreateIntegrationEvidenceSnapshotRequest(),
            idempotency_key="project-stale",
            if_match='"1"',
        )


def test_public_requests_reject_projection_fact_injection_before_write() -> None:
    store = FakeStore()
    service, _, _ = _service(store)
    with pytest.raises(ValidationError):
        service.create_case(
            context=_context(roles=("integration-case-maker",)),
            request={
                "installationId": INSTALLATION_ID,
                "overlayRevision": "overlay-v1",
                "displayName": "非法",
                "evidence": [],
                "computedStage": "production_active",
                "cutoffAt": NOW,
                "metrics": {},
            },  # type: ignore[arg-type]
            idempotency_key="never-written",
        )
    with pytest.raises(ValidationError):
        service.create_evidence_snapshot(
            context=_context(roles=("integration-case-projector",)),
            case_id=CASE_ID,
            request={"evidence": [], "computedStage": "production_active"},  # type: ignore[arg-type]
            idempotency_key="never-written",
            if_match='"1"',
        )
    assert store.create_count == store.project_count == 0
    assert store.receipts == {}


def _evidence(*, producer: str = "producer:trusted") -> SourceConnectionEvidence:
    payload = {
        "evidenceId": "66000000-0000-4000-8000-000000000001",
        "revision": 1,
        "evidenceType": "source_connection",
        "seriesKey": "connector:weixin",
        "subjectRef": "connector:weixin",
        "artifactRef": "artifact:connection",
        "artifactHash": ZERO_HASH,
        "outcome": "valid",
        "observedAt": NOW,
        "expiresAt": None,
        "revokedAt": None,
        "requiredMarkings": ["internal"],
        "producer": producer,
        "claims": {
            "connectionRef": "connector:weixin",
            "authMode": "oauth",
            "readProbe": True,
            "tenantBinding": True,
        },
        "recordedAt": NOW,
    }
    hash_payload = dict(payload)
    hash_payload["observedAt"] = NOW.isoformat().replace("+00:00", "Z")
    hash_payload["recordedAt"] = NOW.isoformat().replace("+00:00", "Z")
    payload["evidenceHash"] = canonical_sha256(hash_payload)
    return SourceConnectionEvidence.model_validate(payload)


def test_trusted_evidence_writer_binds_producer_type_and_projects_atomically() -> None:
    store = FakeStore()
    writer = TrustedEvidenceWriter(
        store=store,  # type: ignore[arg-type]
        context=TrustedProducerContext(
            org_id="org",
            project_id="project",
            producer="producer:trusted",
            markings=("internal",),
            evidence_types=(EvidenceType.SOURCE_CONNECTION,),
        ),
    )
    result = writer.write(case_id=CASE_ID, evidence=_evidence())
    assert result.response.etag_version == 2
    assert store.writer_calls[0][1] == "evidence_added"
    with pytest.raises(EvidenceReferenceInvalidError):
        writer.write(case_id=CASE_ID, evidence=_evidence(producer="producer:spoofed"))
