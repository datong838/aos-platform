from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from aos_api.aip_contracts import ArtifactRef, ResourceRef, TenantContext
from aos_api.aip_memory_contracts import (
    KnowledgeQueryResult,
    KnowledgeScope,
    KnowledgeSourceRef,
    MemoryCandidate,
    MemoryCandidateStatus,
    MemoryItem,
    MemoryItemRevision,
    RuntimeMemoryLayer,
    SubmitMemoryCandidateRequest,
)
from aos_api.auth import Principal, require_principal
from aos_api.routers.aip_memory_authority import (
    get_aip_memory_governance_service,
    get_aip_memory_retrieval_service,
    get_aip_memory_store,
)
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 8, 12, 16, tzinfo=UTC)
HASH = "a" * 64
SCOPE = TenantScope("org-org", "dev-project")


def resource(kind: str, identifier: str) -> ResourceRef:
    return ResourceRef(
        resource_type=kind,
        resource_id=identifier,
        revision="1",
        authority="postgresql",
    )


def artifact(identifier: str, artifact_type: str = "memory_payload") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=identifier,
        artifact_type=artifact_type,
        revision="1",
        content_hash=HASH,
    )


def candidate() -> MemoryCandidate:
    return MemoryCandidate(
        tenant=TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id),
        candidate_id="candidate-1",
        status=MemoryCandidateStatus.PENDING,
        scope=KnowledgeScope.WORKSPACE,
        request=SubmitMemoryCandidateRequest(
            candidate_layer=RuntimeMemoryLayer.SEMANTIC,
            task_id="task-1",
            run_id="run-1",
            subject=resource("ecom.product", "product-1"),
            payload=artifact("payload-1"),
            source=KnowledgeSourceRef(
                source_kind="authorized_document",
                source_uri="urn:source:1",
                observed_at=NOW - timedelta(days=1),
                freshness_expires_at=NOW + timedelta(days=30),
                license_id="internal",
                usage_policy="summary-and-citation",
                content_hash=HASH,
                provider="pytest",
                provider_version="1",
                applicability=["skill:content"],
            ),
            confidence=0.9,
            marking=["internal"],
        ),
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )


def memory() -> tuple[MemoryItem, MemoryItemRevision]:
    tenant = TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id)
    item = MemoryItem(
        tenant=tenant,
        memory_item_id="memory-1",
        memory_layer="semantic",
        scope="workspace",
        status="active",
        subject=resource("ecom.product", "product-1"),
        current_revision=1,
        version=1,
        created_at=NOW,
        updated_at=NOW,
    )
    revision = MemoryItemRevision(
        tenant=tenant,
        memory_item_id=item.memory_item_id,
        revision=1,
        candidate_id="candidate-1",
        source_id="source-1",
        source_revision=1,
        payload=artifact("payload-1"),
        content_hash=HASH,
        confidence=0.9,
        applicability=["skill:content"],
        markings=["internal"],
        effective_at=NOW,
        created_by="pytest",
        created_at=NOW,
    )
    return item, revision


@pytest.fixture()
def memory_api(client):
    class FakeStore:
        def __init__(self) -> None:
            self.scopes: list[TenantScope] = []

        def _record(self, scope):
            self.scopes.append(scope)

        def list_candidates(self, scope, **_kwargs):
            self._record(scope)
            return [candidate()]

        def get_candidate(self, scope, _candidate_id):
            self._record(scope)
            return candidate()

        def list_candidate_events(self, scope, _candidate_id):
            self._record(scope)
            return []

        def list_memory_items(self, scope, **_kwargs):
            self._record(scope)
            return [memory()]

        def get_memory_item(self, scope, _memory_item_id):
            self._record(scope)
            return memory()

    class FakeRetrieval:
        def __init__(self) -> None:
            self.call = None

        def query(self, scope, body, **kwargs):
            self.call = (scope, body, kwargs)
            return KnowledgeQueryResult(
                citations=[], chunks=[], status="blocked",
                blocked_reasons=["knowledge_not_found"], assembled_tokens=0,
            )

    store = FakeStore()
    retrieval = FakeRetrieval()
    client.app.dependency_overrides[require_principal] = lambda: Principal(
        subject="user:qyh",
        org_id=SCOPE.org_id,
        project_id=SCOPE.project_id,
        roles=["admin", "developer"],
        markings=["public", "internal"],
    )
    client.app.dependency_overrides[get_aip_memory_store] = lambda: store
    client.app.dependency_overrides[get_aip_memory_retrieval_service] = lambda: retrieval
    yield client, store, retrieval
    for dependency in (
        require_principal,
        get_aip_memory_store,
        get_aip_memory_retrieval_service,
        get_aip_memory_governance_service,
    ):
        client.app.dependency_overrides.pop(dependency, None)


def query_body() -> dict:
    return {
        "subject": resource("ecom.product", "product-1").model_dump(
            mode="json", by_alias=True
        ),
        "taskId": "task-1",
        "skillRef": resource("aip.skill", "content").model_dump(
            mode="json", by_alias=True
        ),
        "objectRefs": [],
        "timeCutoff": NOW.isoformat(),
        "markings": ["internal"],
        "maxTokens": 256,
    }


def test_read_api_uses_authenticated_tenant_scope(memory_api) -> None:
    client, store, _retrieval = memory_api
    candidates = client.get("/v1/aip/memory-authority/candidates")
    memories = client.get("/v1/aip/memory-authority/memories")
    assert candidates.status_code == 200
    assert candidates.json()[0]["candidateId"] == "candidate-1"
    assert memories.status_code == 200
    assert memories.json()[0]["item"]["memoryItemId"] == "memory-1"
    assert store.scopes == [SCOPE, SCOPE]


def test_knowledge_query_uses_principal_markings_and_derived_skill(memory_api) -> None:
    client, _store, retrieval = memory_api
    response = client.post(
        "/v1/aip/memory-authority/knowledge-queries", json=query_body()
    )
    assert response.status_code == 200
    assert response.json()["status"] == "blocked"
    assert retrieval.call[0] == SCOPE
    assert retrieval.call[2] == {
        "authorized_markings": ["public", "internal"],
        "required_applicability": ["skill:content"],
    }


def test_request_cannot_inject_tenant_fields(memory_api) -> None:
    client, _store, _retrieval = memory_api
    response = client.post(
        "/v1/aip/memory-authority/knowledge-queries",
        json={**query_body(), "orgId": "dev-org", "projectId": "other"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "VALIDATION"


def test_role_check_precedes_unavailable_governance_provider(memory_api) -> None:
    client, _store, _retrieval = memory_api
    client.app.dependency_overrides[require_principal] = lambda: Principal(
        subject="reader",
        org_id=SCOPE.org_id,
        project_id=SCOPE.project_id,
        roles=["developer"],
        markings=["internal"],
    )
    response = client.post(
        "/v1/aip/memory-authority/candidates/candidate-1/approve",
        json={
            "expectedVersion": 1,
            "requiredApplicability": ["skill:content"],
            "governance": {
                "evalReport": artifact("report-1", "eval_report").model_dump(
                    mode="json", by_alias=True
                ),
                "draft": resource("aip.draft", "draft-1").model_dump(
                    mode="json", by_alias=True
                ),
                "approvalEvent": resource(
                    "aip.approval_event", "approval-1"
                ).model_dump(mode="json", by_alias=True),
            },
        },
    )
    assert response.status_code == 403
    assert response.json()["code"] == "AIP_SCOPE_FORBIDDEN"


def test_trusted_provider_absence_is_explicit_503(memory_api) -> None:
    client, _store, _retrieval = memory_api
    client.app.dependency_overrides.pop(get_aip_memory_retrieval_service, None)
    response = client.post(
        "/v1/aip/memory-authority/knowledge-queries", json=query_body()
    )
    assert response.status_code == 503
    assert response.json()["code"] == "AIP_MEMORY_RETRIEVAL_UNAVAILABLE"
