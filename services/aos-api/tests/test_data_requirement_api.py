"""BI-W2-05 Principal-bound canonical DataRequirement API tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.auth import Principal, require_principal
from aos_api.data_requirement_contracts import DataRequirementRevisionRecord
from aos_api.data_requirement_store import DataRequirementApplyResult, canonical_revision_content_hash
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.errors import register_exception_handlers
from aos_api.routers import data_requirements


NOW = datetime(2026, 8, 26, 4, 0, tzinfo=UTC)


def _ref(kind: str, identifier: str, revision: int = 1):
    return {"resourceType": kind, "resourceId": identifier, "revision": revision, "contentHash": f"sha256:{'b' * 64}"}


def _revision(revision: int = 1, status: str = "requested", *, actor: str = "user:data-owner") -> DataRequirementRevisionRecord:
    raw = {
        "tenant": {"orgId": "org-org", "projectId": "dev-project"}, "requirementId": "requirement-1", "revision": revision,
        "priorRef": None if revision == 1 else _ref("DataRequirementRevision", "requirement-1", revision - 1),
        "contentHash": f"sha256:{'a' * 64}", "status": status,
        "caseRef": _ref("BusinessInvestigationCaseRevision", "case-1"), "runRef": _ref("BusinessInvestigationRun", "run-1"),
        "checkpointRef": _ref("CheckpointRevision", "checkpoint-1"), "purposeCode": "business_portrait_gap",
        "channelRef": _ref("ChannelRevision", "channel-niushop"), "entityRef": _ref("BusinessEntityRevision", "shop-qyh"),
        "requiredFacts": ["Order"], "timeWindow": {"startAt": NOW - timedelta(days=1), "endAt": NOW}, "grain": "day",
        "cutoffAt": NOW, "freshnessMaxAgeSeconds": 3600, "qualityThreshold": 0.95, "markings": ["INTERNAL"],
        "piiAllowed": False, "minPopulation": 20, "requestedOutputs": ["DataProductRevision"], "budgetMinor": 1000,
        "expiresAt": NOW + timedelta(days=1), "createdBy": actor, "createdAt": NOW, "blockers": [],
    }
    parsed = DataRequirementRevisionRecord.model_validate(raw)
    return parsed.model_copy(update={"content_hash": canonical_revision_content_hash(parsed)})


class FakeStore:
    def __init__(self): self.current = _revision(); self.calls = []
    def get_current(self, scope, requirement_id): self.calls.append(("get", scope.key, requirement_id)); return self.current
    def list_fulfillment_receipts(self, scope, requirement_id): self.get_current(scope, requirement_id); return []
    def request(self, scope, actor, key, item, *, expected_version):
        self.calls.append(("request", scope.key, actor, key, expected_version))
        return DataRequirementApplyResult(InvestigationExactRef(resourceType="DataRequirementRevision", resourceId=item.requirement_id, revision=1, contentHash=item.content_hash), 1, item.content_hash, False)
    def accept(self, scope, actor, key, item, *, expected_version):
        self.calls.append(("accept", scope.key, actor, key, expected_version)); self.current = item
        return DataRequirementApplyResult(InvestigationExactRef(resourceType="DataRequirementRevision", resourceId=item.requirement_id, revision=2, contentHash=item.content_hash), 2, item.content_hash, False)
    reject = accept
    cancel = accept


def _client(store: FakeStore, *, roles=("data-owner",)) -> TestClient:
    app = FastAPI(); register_exception_handlers(app); app.include_router(data_requirements.router)
    app.dependency_overrides[require_principal] = lambda: Principal(subject="user:data-owner", org_id="org-org", project_id="dev-project", roles=list(roles))
    app.dependency_overrides[data_requirements.get_data_requirement_store] = lambda: store
    return TestClient(app, raise_server_exceptions=False)


def test_create_get_receipts_are_principal_bound_and_exact_etag():
    store = FakeStore(); first = _revision()
    with _client(store) as client:
        created = client.post("/v1/data/requirements", headers={"Idempotency-Key": "create-1"}, json={"expectedVersion": 0, "revision": first.model_dump(mode="json", by_alias=True)})
        assert created.status_code == 200
        assert created.headers["etag"] == f'"{first.content_hash}"'
        got = client.get("/v1/data/requirements/requirement-1")
        assert got.status_code == 200 and got.json()["tenant"]["orgId"] == "org-org"
        receipts = client.get("/v1/data/requirements/requirement-1/receipts")
        assert receipts.status_code == 200 and receipts.json() == []
    assert store.calls[0][1] == ("org-org", "dev-project")


def test_write_role_path_id_and_etag_fail_closed():
    store = FakeStore(); first = _revision(); second = _revision(2, "accepted")
    payload = {"expectedVersion": 1, "revision": second.model_dump(mode="json", by_alias=True)}
    with _client(store, roles=("viewer",)) as client:
        assert client.post("/v1/data/requirements/requirement-1:accept", headers={"Idempotency-Key": "accept-1", "If-Match": f'"{first.content_hash}"'}, json=payload).status_code == 403
    with _client(store) as client:
        assert client.post("/v1/data/requirements/wrong:accept", headers={"Idempotency-Key": "accept-1", "If-Match": f'"{first.content_hash}"'}, json=payload).status_code == 409
        stale = client.post("/v1/data/requirements/requirement-1:accept", headers={"Idempotency-Key": "accept-1", "If-Match": '"sha256:' + "0" * 64 + '"'}, json=payload)
        assert stale.status_code == 409 and stale.json()["code"] == "DATA_REQUIREMENT_ETAG_CONFLICT"


def test_missing_bearer_contract_remains_declared_in_openapi():
    app = FastAPI(); app.include_router(data_requirements.router)
    operation_ids = [op["operationId"] for path in app.openapi()["paths"].values() for op in path.values() if isinstance(op, dict) and "operationId" in op]
    assert len(operation_ids) == len(set(operation_ids))
    assert {"dataRequirementCreate", "dataRequirementGet", "dataRequirementAccept", "dataRequirementReject", "dataRequirementCancel", "dataRequirementReceiptList"} <= set(operation_ids)
