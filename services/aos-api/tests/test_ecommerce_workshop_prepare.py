from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.aip_production_contract_store import canonical_hash
from aos_api.aip_production_contracts import (
    BriefLifecycle,
    CreateBriefRequest,
    ExactRevisionRef,
    ReviseBriefRequest,
    TaskBriefRevision,
)
from aos_api.aip_production_profile_contracts import ProductionProfile
from aos_api.auth import Principal, require_principal
from aos_api.ecommerce_workshop_prepare_contracts import (
    EcommerceWorkshopPrepareRequest,
)
from aos_api.ecommerce_workshop_prepare_service import (
    EcommerceWorkshopPrepareService,
    PrepareConflict,
    PrepareDependencyBlocked,
)
from aos_api.ecommerce_workshop_prepare_store import (
    EcommerceWorkshopPrepareStore,
    PreparationIdempotencyConflict,
    PreparationRecord,
)
from aos_api.errors import register_exception_handlers
from aos_api.routers import ecommerce_workshop
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 8, 24, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")
PROFILE_REF = ExactRevisionRef(
    resource_type="ProductionProfileRevision",
    resource_id=(
        "bundle://aos/solution.ecommerce.growth@1.4.0/"
        "content/production-profiles/ecommerce.content-campaign.json"
    ),
    revision=1,
    content_hash="a" * 64,
)


def _profile() -> ProductionProfile:
    return ProductionProfile.model_validate(
        {
            "schema": "aos.ecommerce-production-profile/v1",
            "moduleId": "ecommerce.content-campaign",
            "profileRevision": 1,
            "brief": {
                "mode": "owned",
                "briefType": "campaign-content",
                "requiredFields": ["objective"],
                "sourceResponsibilityPreserved": True,
            },
            "evidenceSelection": {
                "requiredFacts": ["audienceEvidence", "brandPolicy"],
                "requireProvenance": True,
                "requireFreshness": True,
                "requireNegativeEvidence": True,
            },
            "eval": {
                "gates": ["fact", "brand", "approval"],
                "failClosed": True,
                "sameRevisionRequired": True,
            },
            "responsibility": {
                "slots": [
                    {
                        "slotId": "content.owner",
                        "responsibilityType": "maker",
                        "atomicSkillIds": ["strategy.plan", "copy.generate"],
                        "protected": False,
                        "mergeAllowed": True,
                        "returnStage": "prepare",
                    },
                    {
                        "slotId": "content.review",
                        "responsibilityType": "independent_review",
                        "atomicSkillIds": ["content.review"],
                        "protected": True,
                        "mergeAllowed": False,
                        "returnStage": "prepare",
                    },
                ],
                "handoffRequired": True,
                "reassignmentRequiresCanonicalDecision": True,
            },
            "contributionProjection": {
                "showAtomicSkillAttribution": True,
                "showLogicRevision": True,
                "showCoworkerBinding": True,
                "showBlockers": True,
            },
        }
    )


def _request(**updates: Any) -> EcommerceWorkshopPrepareRequest:
    payload: dict[str, Any] = {
        "brief": {
            "taskId": "task-1",
            "briefType": "campaign-content",
            "schemaRef": {
                "resourceType": "JsonSchema",
                "resourceId": "campaign-content",
                "revision": "1",
                "authority": "asset-registry",
            },
            "spec": {"objective": "launch"},
        },
        "subjectRefs": [],
        "canonicalEvidenceRefs": [],
        "cutoffAt": NOW.isoformat(),
        "purpose": "campaign preparation",
        "marking": ["public"],
        "productionProfileRef": PROFILE_REF.model_dump(mode="json", by_alias=True),
    }
    payload.update(updates)
    return EcommerceWorkshopPrepareRequest.model_validate(payload)


class MemoryPreparationStore:
    def __init__(self) -> None:
        self.records: dict[tuple[tuple[str, str], str], PreparationRecord] = {}
        self.counter = 0

    def begin(self, scope: TenantScope, **kwargs: Any) -> PreparationRecord:
        key = (scope.key, kwargs["idempotency_key"])
        current = self.records.get(key)
        if current:
            if current.request_hash != kwargs["request_hash"]:
                raise PreparationIdempotencyConflict("different request")
            return current
        self.counter += 1
        record = PreparationRecord(
            preparation_id=f"preparation-{self.counter}",
            module_id=kwargs["module_id"],
            request_hash=kwargs["request_hash"],
            status="pending",
            result_body=None,
        )
        self.records[key] = record
        return record

    def complete(self, scope: TenantScope, **kwargs: Any) -> PreparationRecord:
        key = next(
            key
            for key, value in self.records.items()
            if key[0] == scope.key and value.preparation_id == kwargs["preparation_id"]
        )
        current = self.records[key]
        completed = PreparationRecord(
            preparation_id=current.preparation_id,
            module_id=current.module_id,
            request_hash=current.request_hash,
            status="complete",
            result_body=kwargs["result_body"],
        )
        self.records[key] = completed
        return completed


class FakeBriefAuthority:
    def __init__(self) -> None:
        self.create_count = 0
        self.revise_count = 0
        self.current: TaskBriefRevision | None = None
        self.history: dict[int, TaskBriefRevision] = {}

    def create_brief(
        self, scope: TenantScope, actor: str, key: str, body: CreateBriefRequest
    ) -> TaskBriefRevision:
        self.create_count += 1
        self.current = self._revision(scope, actor, body, revision=1, version=1)
        self.history[1] = self.current
        return self.current

    def revise_brief(
        self,
        scope: TenantScope,
        actor: str,
        brief_id: str,
        key: str,
        body: ReviseBriefRequest,
    ) -> TaskBriefRevision:
        assert self.current and self.current.brief_id == brief_id
        if body.expected_version != self.current.version:
            from aos_api.aip_production_contract_store import ProductionContractConflict

            raise ProductionContractConflict("stale task brief version")
        self.revise_count += 1
        request = CreateBriefRequest(
            task_id=self.current.task_id,
            brief_type=body.brief_type,
            schema_ref=body.schema_ref,
            spec=body.spec,
        )
        self.current = self._revision(
            scope, actor, request, revision=self.current.revision + 1, version=self.current.version + 1
        )
        self.history[self.current.revision] = self.current
        return self.current

    def get_brief(
        self, scope: TenantScope, brief_id: str, revision: int | None = None
    ) -> TaskBriefRevision:
        assert self.current and self.current.tenant.org_id == scope.org_id
        return self.history[revision] if revision is not None else self.current

    @staticmethod
    def _revision(
        scope: TenantScope,
        actor: str,
        body: CreateBriefRequest,
        *,
        revision: int,
        version: int,
    ) -> TaskBriefRevision:
        content_hash = canonical_hash(
            {
                "briefType": body.brief_type,
                "schemaRef": body.schema_ref.model_dump(mode="json", by_alias=True),
                "spec": body.spec,
            }
        )
        return TaskBriefRevision(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            brief_id="brief-1",
            task_id=body.task_id,
            revision=revision,
            version=version,
            brief_type=body.brief_type,
            schema_ref=body.schema_ref,
            spec=body.spec,
            content_hash=content_hash,
            lifecycle=BriefLifecycle.DRAFT,
            created_by=actor,
            created_at=NOW,
        )


def _service(
    *, profile: ProductionProfile | None = None
) -> tuple[EcommerceWorkshopPrepareService, MemoryPreparationStore, FakeBriefAuthority]:
    preparations = MemoryPreparationStore()
    briefs = FakeBriefAuthority()
    service = EcommerceWorkshopPrepareService(
        preparation_store=preparations,  # type: ignore[arg-type]
        brief_authority=briefs,
        profile_reader=lambda scope, ref: _profile() if profile is None else profile,
    )
    return service, preparations, briefs


def test_prepare_creates_only_draft_request_recommendation_and_zero_effect_receipt() -> None:
    service, _, briefs = _service()
    result = service.prepare(
        SCOPE,
        actor="user:test",
        module_id="ecommerce.content-campaign",
        idempotency_key="prepare-1",
        body=_request(),
    )
    assert result.tenant == TenantContext(org_id="org-org", project_id="dev-project")
    assert result.draft_brief_ref.resource_type == "TaskBriefRevision"
    assert result.evidence_build_request.readiness == "blocked"
    assert result.evidence_build_request.missing_fact_ids == [
        "audienceEvidence",
        "brandPolicy",
    ]
    review = result.responsibility_recommendation.slots[1]
    assert review.atomic_skill_ids == ["content.review"]
    assert review.protected is True and review.merge_allowed is False
    assert result.responsibility_recommendation.uncovered_slot_ids == [
        "content.owner",
        "content.review",
    ]
    assert result.receipt.output_counts["evidenceBundles"] == 0
    assert result.receipt.output_counts["responsibilityPlans"] == 0
    assert set(result.receipt.side_effects.model_dump().values()) == {0}
    assert result.receipt.next_allowed_commands == []
    assert briefs.create_count == 1 and briefs.revise_count == 0


def test_prepare_same_key_replays_and_different_hash_conflicts_without_duplicate_brief() -> None:
    service, _, briefs = _service()
    first = service.prepare(
        SCOPE,
        actor="user:test",
        module_id="ecommerce.content-campaign",
        idempotency_key="same-key",
        body=_request(),
    )
    replay = service.prepare(
        SCOPE,
        actor="user:test",
        module_id="ecommerce.content-campaign",
        idempotency_key="same-key",
        body=_request(),
    )
    assert replay.receipt.preparation_id == first.receipt.preparation_id
    assert replay.receipt.replay is True
    assert briefs.create_count == 1
    with pytest.raises(PrepareConflict):
        service.prepare(
            SCOPE,
            actor="user:test",
            module_id="ecommerce.content-campaign",
            idempotency_key="same-key",
            body=_request(purpose="another purpose"),
        )


def test_prepare_revision_uses_exact_draft_and_stale_version_fails_closed() -> None:
    service, _, briefs = _service()
    first = service.prepare(
        SCOPE,
        actor="user:test",
        module_id="ecommerce.content-campaign",
        idempotency_key="create",
        body=_request(),
    )
    exact = first.draft_brief_ref.model_dump(mode="json", by_alias=True)
    revise = _request(
        brief={
            "taskId": "task-1",
            "briefType": "campaign-content",
            "schemaRef": {
                "resourceType": "JsonSchema",
                "resourceId": "campaign-content",
                "revision": "1",
                "authority": "asset-registry",
            },
            "spec": {"objective": "launch revised"},
            "existingBriefRef": exact,
            "expectedVersion": 1,
        }
    )
    changed = service.prepare(
        SCOPE,
        actor="user:test",
        module_id="ecommerce.content-campaign",
        idempotency_key="revise",
        body=revise,
    )
    assert changed.draft_brief_ref.revision == 2
    assert changed.brief_diff[0].field == "spec"
    with pytest.raises(PrepareConflict):
        service.prepare(
            SCOPE,
            actor="user:test",
            module_id="ecommerce.content-campaign",
            idempotency_key="stale",
            body=revise,
        )
    assert briefs.revise_count == 1


def test_missing_or_wrong_module_installed_profile_fails_closed() -> None:
    store = MemoryPreparationStore()
    service = EcommerceWorkshopPrepareService(
        preparation_store=store,  # type: ignore[arg-type]
        brief_authority=FakeBriefAuthority(),
        profile_reader=lambda scope, ref: None,
    )
    with pytest.raises(PrepareDependencyBlocked):
        service.prepare(
            SCOPE,
            actor="user:test",
            module_id="ecommerce.content-campaign",
            idempotency_key="blocked",
            body=_request(),
        )


def test_prepare_request_forbids_tenant_secret_and_non_exact_profile_injection() -> None:
    base = _request().model_dump(mode="json", by_alias=True)
    with pytest.raises(ValidationError):
        EcommerceWorkshopPrepareRequest.model_validate({**base, "orgId": "dev-org"})
    with pytest.raises(ValidationError):
        EcommerceWorkshopPrepareRequest.model_validate({**base, "providerSecret": "x"})
    bad = {**base, "productionProfileRef": {**base["productionProfileRef"], "revision": None}}
    with pytest.raises(ValidationError):
        EcommerceWorkshopPrepareRequest.model_validate(bad)


def test_prepare_route_uses_principal_tenant_and_exposes_canonical_operation() -> None:
    service, _, _ = _service()
    seen: list[tuple[str, str]] = []

    class RecordingService:
        def prepare(self, scope: TenantScope, **kwargs: Any):
            seen.append(scope.key)
            return service.prepare(scope, **kwargs)

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(ecommerce_workshop.router)
    app.dependency_overrides[require_principal] = lambda: Principal(
        subject="user:test",
        org_id="org-org",
        project_id="dev-project",
        roles=["operator"],
        markings=["public"],
    )
    app.dependency_overrides[
        ecommerce_workshop.get_ecommerce_workshop_prepare_service
    ] = RecordingService
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/v1/ecommerce-workshop/modules/ecommerce.content-campaign/commands/prepare",
            headers={"Idempotency-Key": "route-1"},
            json=_request().model_dump(mode="json", by_alias=True),
        )
        assert response.status_code == 200, response.text
        assert response.json()["tenant"] == {
            "orgId": "org-org",
            "projectId": "dev-project",
        }
        assert client.post(
            "/v1/ecommerce-workshop/modules/ecommerce.content-campaign/commands/prepare?orgId=dev-org",
            headers={"Idempotency-Key": "route-2"},
            json=_request().model_dump(mode="json", by_alias=True),
        ).status_code == 400
    assert seen == [("org-org", "dev-project")]
    operation = app.openapi()["paths"][
        "/v1/ecommerce-workshop/modules/{module_id}/commands/prepare"
    ]["post"]
    assert operation["operationId"] == "ecommerceWorkshopPrepare"


class _DbResult:
    def __init__(self, row: dict[str, Any] | None = None) -> None:
        self.row = row

    def fetchone(self) -> dict[str, Any] | None:
        return self.row


class _DbConnection:
    def __init__(self, results: list[dict[str, Any] | None]) -> None:
        self.results = list(results)
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.commits = 0

    def execute(self, query: str, params: tuple[object, ...]) -> _DbResult:
        self.calls.append((" ".join(query.split()), params))
        return _DbResult(self.results.pop(0) if self.results else None)

    def commit(self) -> None:
        self.commits += 1


def test_postgres_store_persists_tenant_scoped_intent_then_immutable_result() -> None:
    pending = {
        "preparation_id": "preparation-db-1",
        "module_id": "ecommerce.content-campaign",
        "request_hash": "request-hash",
        "status": "pending",
    }
    connection = _DbConnection(
        [
            None,
            pending,
            pending,
            None,
            None,
            None,
        ]
    )

    @contextmanager
    def connect(scope: TenantScope):
        assert scope.key == ("org-org", "dev-project")
        yield connection

    store = EcommerceWorkshopPrepareStore(connect_factory=connect)
    started = store.begin(
        SCOPE,
        actor="user:test",
        module_id="ecommerce.content-campaign",
        idempotency_key="db-key",
        request_hash="request-hash",
        request_body={"purpose": "prepare"},
    )
    completed = store.complete(
        SCOPE,
        actor="user:test",
        preparation_id=started.preparation_id,
        request_hash="request-hash",
        result_hash="result-hash",
        result_body={"readiness": "blocked"},
    )

    assert started.status == "pending"
    assert completed.status == "complete"
    assert completed.result_body == {"readiness": "blocked"}
    assert connection.commits == 2
    assert all(
        call[1][:2] == ("org-org", "dev-project")
        for call in connection.calls
        if "aip_workshop_preparation" in call[0]
    )
    assert any(
        "INSERT INTO aip_workshop_preparation_result" in query
        for query, _ in connection.calls
    )


def test_postgres_store_replay_and_hash_drift_fail_closed() -> None:
    existing = {
        "preparation_id": "preparation-db-1",
        "module_id": "ecommerce.content-campaign",
        "request_hash": "request-hash",
        "status": "complete",
        "result_body": '{"readiness":"blocked"}',
    }
    connection = _DbConnection([existing, existing])

    @contextmanager
    def connect(scope: TenantScope):
        assert scope == SCOPE
        yield connection

    store = EcommerceWorkshopPrepareStore(connect_factory=connect)
    replay = store.begin(
        SCOPE,
        actor="user:test",
        module_id="ecommerce.content-campaign",
        idempotency_key="db-key",
        request_hash="request-hash",
        request_body={},
    )
    assert replay.result_body == {"readiness": "blocked"}
    with pytest.raises(PreparationIdempotencyConflict):
        store.begin(
            SCOPE,
            actor="user:test",
            module_id="ecommerce.content-campaign",
            idempotency_key="db-key",
            request_hash="another-hash",
            request_body={},
        )
    assert connection.commits == 0
