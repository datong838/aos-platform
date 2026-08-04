from __future__ import annotations

import uuid

import pytest
from aos_api import data_os_store as dos
from aos_api.db import connect
from aos_api.errors import ApiError
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


@pytest.mark.parametrize(
    ("persist", "args"),
    [
        (dos.persist_source, ({"id": "missing", "type": "file"},)),
        (
            dos.persist_pipeline,
            ({"id": "missing", "sourceId": "source", "target": "dataset"},),
        ),
        (dos.persist_dataset, ({"rid": "missing", "name": "missing"},)),
        (dos.persist_sync, ({"id": "missing", "sourceId": "source"},)),
        (dos.persist_schedule, ({"id": "missing"},)),
        (dos.persist_dataset_history, ("missing", [])),
    ],
)
def test_d2a_persist_requires_tenant_scope(persist, args) -> None:
    with pytest.raises(ApiError) as missing:
        persist(None, *args)
    assert missing.value.code == "TENANT_SCOPE_REQUIRED"


def test_d2a_six_persist_paths_write_explicit_scope() -> None:
    suffix = uuid.uuid4().hex
    scope = TenantScope(f"org-d2a-{suffix}", f"project-d2a-{suffix}")
    _ensure_scope(scope)
    source_id = f"source-{suffix}"
    pipeline_id = f"pipeline-{suffix}"
    dataset_rid = f"dataset-{suffix}"
    sync_id = f"sync-{suffix}"
    schedule_id = f"schedule-{suffix}"

    dos.persist_source(scope, {"id": source_id, "type": "file"})
    dos.persist_pipeline(
        scope,
        {
            "id": pipeline_id,
            "sourceId": source_id,
            "target": "dataset",
            "datasetRid": dataset_rid,
        },
    )
    dos.persist_dataset(
        scope,
        {
            "rid": dataset_rid,
            "name": dataset_rid,
            "pipelineId": pipeline_id,
            "sourceId": source_id,
        },
    )
    dos.persist_sync(scope, {"id": sync_id, "sourceId": source_id})
    dos.persist_schedule(
        scope, {"id": schedule_id, "pipelineId": pipeline_id, "enabled": True}
    )
    dos.persist_dataset_history(scope, dataset_rid, [{"version": 1}])

    checks = {
        "meta_source": ("id", source_id),
        "meta_pipeline": ("id", pipeline_id),
        "meta_dataset": ("rid", dataset_rid),
        "meta_sync": ("id", sync_id),
        "meta_schedule": ("id", schedule_id),
        "meta_dataset_history": ("dataset_rid", dataset_rid),
    }
    with connect() as conn:
        for table, (key, value) in checks.items():
            rows = conn.execute(
                f"SELECT DISTINCT org_id,project_id FROM {table} WHERE {key}=%s",
                (value,),
            ).fetchall()
            assert {(row["org_id"], row["project_id"]) for row in rows} == {
                scope.key
            }
    dos.delete_schedule(scope, schedule_id)
    dos.delete_sync(scope, sync_id)
    dos.delete_dataset(scope, dataset_rid)
    dos.delete_pipeline(scope, pipeline_id)
    dos.delete_source(scope, source_id)


def test_d2a_same_source_id_coexists_without_overwriting_other_scope() -> None:
    suffix = uuid.uuid4().hex
    scope_a = TenantScope(f"org-a-{suffix}", f"project-a-{suffix}")
    scope_b = TenantScope(f"org-b-{suffix}", f"project-b-{suffix}")
    _ensure_scope(scope_a)
    _ensure_scope(scope_b)
    source_id = f"shared-source-{suffix}"
    dos.persist_source(scope_a, {"id": source_id, "type": "file", "status": "A"})

    dos.persist_source(scope_b, {"id": source_id, "type": "file", "status": "B"})

    with connect() as conn:
        rows = conn.execute(
            "SELECT org_id,project_id,status FROM meta_source WHERE id=%s",
            (source_id,),
        ).fetchall()
    assert {
        (row["org_id"], row["project_id"], row["status"]) for row in rows
    } == {(*scope_a.key, "A"), (*scope_b.key, "B")}
    dos.delete_source(scope_a, source_id)
    dos.delete_source(scope_b, source_id)


def test_d2a_history_replace_keeps_other_scope_rows() -> None:
    suffix = uuid.uuid4().hex
    scope_a = TenantScope(f"org-ha-{suffix}", f"project-ha-{suffix}")
    scope_b = TenantScope(f"org-hb-{suffix}", f"project-hb-{suffix}")
    _ensure_scope(scope_a)
    _ensure_scope(scope_b)
    rid = f"history-{suffix}"
    dos.persist_dataset(scope_a, {"rid": rid, "name": "A"})
    dos.persist_dataset(scope_b, {"rid": rid, "name": "B"})
    dos.persist_dataset_history(scope_a, rid, [{"version": 1}])
    dos.persist_dataset_history(scope_b, rid, [{"version": 9}])
    dos.persist_dataset_history(scope_a, rid, [{"version": 2}])

    with connect() as conn:
        rows = conn.execute(
            "SELECT org_id,project_id,payload FROM meta_dataset_history "
            "WHERE dataset_rid=%s ORDER BY org_id",
            (rid,),
        ).fetchall()
    assert {
        (row["org_id"], row["project_id"], int(row["payload"]["version"]))
        for row in rows
    } == {(*scope_a.key, 2), (*scope_b.key, 9)}
    dos.delete_dataset(scope_a, rid)
    dos.delete_dataset(scope_b, rid)
