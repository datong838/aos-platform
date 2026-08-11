from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aos_api.aip_contracts import TenantContext
from aos_api.aip_eval_authority_store import (
    AipEvalAuthorityNotFound,
    AipEvalAuthorityPersistenceError,
)
from aos_api.aip_eval_contracts import (
    AssetRevisionRef,
    AssetType,
    DatasetRevisionRef,
    EvalRunAuthorityRecord,
    EvalRunStatus,
    EvidenceQuality,
    JudgeRevisionRef,
    LineageEvent,
    LineageEventType,
    LineageRootType,
)
from aos_api.routers.aip_eval_authority import (
    get_aip_eval_authority_store,
    router,
)
from aos_api.tenant_scope import TenantScope

HASH = "a" * 64
NOW = datetime(2026, 8, 11, tzinfo=UTC)


@pytest.fixture()
def eval_authority_api(client):
    client.app.include_router(router)
    tenant = TenantContext(org_id="dev-org", project_id="dev-project")
    policy = AssetRevisionRef(
        asset_type=AssetType.POLICY,
        asset_id="redaction-1",
        revision="1",
        content_hash=HASH,
    )
    dataset = DatasetRevisionRef(
        dataset_id="dataset-1",
        revision=1,
        content_hash=HASH,
        source_hash="b" * 64,
        redaction_policy=policy,
    )
    run = EvalRunAuthorityRecord(
        tenant=tenant,
        run_id="run-1",
        suite_ref=AssetRevisionRef(
            asset_type=AssetType.EVAL_SUITE,
            asset_id="suite-1",
            revision="1",
            content_hash=HASH,
        ),
        target=AssetRevisionRef(
            asset_type=AssetType.LOGIC_GRAPH,
            asset_id="logic-1",
            revision="1",
            content_hash=HASH,
        ),
        dataset=dataset,
        judge=JudgeRevisionRef(judge_id="judge-1", revision=1, content_hash=HASH),
        status=EvalRunStatus.QUEUED,
        idempotency_key="run-once",
        created_by="user:dev",
        created_at=NOW,
        version=1,
    )
    lineage = LineageEvent(
        tenant=tenant,
        event_id="lineage-event-1",
        lineage_id="lineage-1",
        root_type=LineageRootType.TASK_RUN,
        root_id=run.run_id,
        sequence=1,
        event_type=LineageEventType.EVAL,
        payload_hash=HASH,
        quality=EvidenceQuality.MEASURED,
        occurred_at=NOW,
        observed_at=NOW,
    )

    class FakeStore:
        error: Exception | None = None
        scopes: list[TenantScope] = []

        def _record(self, scope: TenantScope):
            self.scopes.append(scope)
            if self.error:
                raise self.error

        def get_dataset_revision(self, scope, _dataset_id, _revision):
            self._record(scope)
            return dataset

        def get_eval_run(self, scope, _run_id):
            self._record(scope)
            return run

        def list_lineage_events(self, scope, _lineage_id):
            self._record(scope)
            return [lineage]

    store = FakeStore()
    client.app.dependency_overrides[get_aip_eval_authority_store] = lambda: store
    headers = {
        "Authorization": "Bearer dev",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
    }
    yield client, store, headers
    client.app.dependency_overrides.pop(get_aip_eval_authority_store, None)


def test_read_routes_use_authenticated_tenant_scope(eval_authority_api) -> None:
    client, store, headers = eval_authority_api
    dataset = client.get(
        "/v1/aip/eval-authority/datasets/dataset-1/revisions/1",
        headers=headers,
    )
    assert dataset.status_code == 200
    assert dataset.json()["datasetId"] == "dataset-1"
    run = client.get("/v1/aip/eval-authority/runs/run-1", headers=headers)
    assert run.status_code == 200
    assert run.json()["tenant"] == {
        "orgId": "dev-org",
        "projectId": "dev-project",
    }
    lineage = client.get(
        "/v1/aip/eval-authority/lineage/lineage-1", headers=headers
    )
    assert lineage.status_code == 200
    assert lineage.json()[0]["quality"] == "measured"
    assert store.scopes == [TenantScope("dev-org", "dev-project")] * 3


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (AipEvalAuthorityNotFound("missing"), 404, "AIP_EVAL_AUTHORITY_NOT_FOUND"),
        (
            AipEvalAuthorityPersistenceError("db"),
            503,
            "AIP_EVAL_AUTHORITY_PERSISTENCE_ERROR",
        ),
    ],
)
def test_read_errors_fail_closed(eval_authority_api, error, status_code, code) -> None:
    client, store, headers = eval_authority_api
    store.error = error
    response = client.get("/v1/aip/eval-authority/runs/run-1", headers=headers)
    assert response.status_code == status_code
    assert response.json()["code"] == code


def test_read_routes_require_authentication(eval_authority_api) -> None:
    client, _store, _headers = eval_authority_api
    response = client.get("/v1/aip/eval-authority/runs/run-1")
    assert response.status_code in {401, 403}
