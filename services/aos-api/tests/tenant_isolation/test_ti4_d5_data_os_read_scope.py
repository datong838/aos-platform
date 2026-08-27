from __future__ import annotations

import uuid

import pytest
from aos_api import data_os_store as dos
from aos_api.auth import Principal
from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.routers import wave_ext
from aos_api.tenant_scope import TenantScope


def _ensure_scope(scope: TenantScope) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org (id,name) VALUES (%s,%s) ON CONFLICT DO NOTHING",
            (scope.org_id, scope.org_id),
        )
        conn.execute(
            "INSERT INTO twa_workspace (org_id,project_id,name) "
            "VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
            (scope.org_id, scope.project_id, scope.project_id),
        )
        conn.commit()


def _principal(scope: TenantScope) -> Principal:
    return Principal(subject="reader", org_id=scope.org_id, project_id=scope.project_id)


def _seed(scope: TenantScope, suffix: str) -> dict[str, str]:
    ids = {
        "source": f"source-{suffix}",
        "pipeline": f"pipeline-{suffix}",
        "dataset": f"dataset-{suffix}",
        "sync": f"sync-{suffix}",
        "schedule": f"schedule-{suffix}",
    }
    dos.persist_source(scope, {"id": ids["source"], "type": "file"})
    dos.persist_pipeline(
        scope,
        {
            "id": ids["pipeline"],
            "sourceId": ids["source"],
            "target": "dataset",
            "datasetRid": ids["dataset"],
            "lastBuild": {"id": f"build-{suffix}", "status": "SUCCEEDED"},
        },
    )
    dos.persist_dataset(
        scope,
        {
            "rid": ids["dataset"],
            "name": ids["dataset"],
            "sourceId": ids["source"],
            "pipelineId": ids["pipeline"],
        },
    )
    dos.persist_dataset_history(scope, ids["dataset"], [{"version": 1}])
    dos.persist_sync(scope, {"id": ids["sync"], "sourceId": ids["source"]})
    dos.persist_schedule(
        scope, {"id": ids["schedule"], "pipelineId": ids["pipeline"]}
    )
    return ids


def _cleanup(scope: TenantScope, ids: dict[str, str]) -> None:
    dos.delete_schedule(scope, ids["schedule"])
    dos.delete_sync(scope, ids["sync"])
    dos.delete_dataset(scope, ids["dataset"])
    dos.delete_pipeline(scope, ids["pipeline"])
    dos.delete_source(scope, ids["source"])


def test_d5_load_all_requires_scope_and_excludes_other_scope() -> None:
    suffix = uuid.uuid4().hex
    scope_a = TenantScope(f"org-{suffix}", f"project-a-{suffix}")
    scope_b = TenantScope(f"org-{suffix}", f"project-b-{suffix}")
    _ensure_scope(scope_a)
    _ensure_scope(scope_b)
    ids_a = _seed(scope_a, f"a-{suffix}")
    ids_b = _seed(scope_b, f"b-{suffix}")
    try:
        with pytest.raises(ApiError) as missing:
            dos.load_all(None)
        assert missing.value.code == "TENANT_SCOPE_REQUIRED"
        loaded_a = dos.load_all(scope_a)
        loaded_b = dos.load_all(scope_b)
        assert set(loaded_a["connectors"]) == {ids_a["source"]}
        assert set(loaded_b["connectors"]) == {ids_b["source"]}
        assert loaded_a["dataset_history"][ids_a["dataset"]] == [{"version": 1}]
    finally:
        _cleanup(scope_a, ids_a)
        _cleanup(scope_b, ids_b)


def test_d5_boot_is_empty_then_router_lazy_loads_strict_workspace_scope() -> None:
    suffix = uuid.uuid4().hex
    scope_a = TenantScope(f"org-{suffix}", f"project-a-{suffix}")
    scope_b = TenantScope(f"org-{suffix}", f"project-b-{suffix}")
    _ensure_scope(scope_a)
    _ensure_scope(scope_b)
    ids_a = _seed(scope_a, f"a-{suffix}")
    ids_b = _seed(scope_b, f"b-{suffix}")
    try:
        dos.boot_data_os(wave_ext)
        assert wave_ext._connectors == {}
        assert wave_ext._pipelines == {}
        assert wave_ext._datasets == {}
        assert wave_ext._syncs == {}
        assert wave_ext._schedules == {}

        sources_a = wave_ext.list_sources(_principal(scope_a))["items"]
        sources_b = wave_ext.list_sources(_principal(scope_b))["items"]
        assert {item["id"] for item in sources_a} == {ids_a["source"]}
        assert {item["id"] for item in sources_b} == {ids_b["source"]}
        assert {item["id"] for item in wave_ext.list_syncs(_principal(scope_a))["items"]} == {
            ids_a["sync"]
        }
        dataset_rids_b = {
            item["rid"] for item in wave_ext.list_datasets(_principal(scope_b))["items"]
        }
        assert ids_b["dataset"] in dataset_rids_b
        assert ids_a["dataset"] not in dataset_rids_b
        assert "ri.aos.main.dataset.P01-shop-qyh" in dataset_rids_b
        assert {
            item["id"] for item in wave_ext.list_pipelines(_principal(scope_a))["items"]
        } == {ids_a["pipeline"]}
        assert {
            item["id"] for item in wave_ext.list_schedules(_principal(scope_b))["items"]
        } == {ids_b["schedule"]}
        with pytest.raises(ApiError) as hidden:
            wave_ext.get_sync(ids_a["sync"], _principal(scope_b))
        assert hidden.value.status_code == 404
    finally:
        dos.boot_data_os(wave_ext)
        _cleanup(scope_a, ids_a)
        _cleanup(scope_b, ids_b)
