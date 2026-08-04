from __future__ import annotations

import uuid
from types import SimpleNamespace

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
    ("mutation", "args"),
    [
        (dos.delete_source, ("missing",)),
        (dos.delete_pipeline, ("missing",)),
        (dos.delete_dataset, ("missing",)),
        (dos.delete_sync, ("missing",)),
        (dos.delete_schedule, ("missing",)),
        (dos.persist_phase5_pipeline_graph, ({"pipeline_id": "missing"},)),
        (dos.load_phase5_pipeline_graph, ("missing",)),
        (dos.delete_phase5_pipeline_graph, ("missing",)),
    ],
)
def test_d2b_graph_and_delete_require_tenant_scope(mutation, args) -> None:
    with pytest.raises(ApiError) as missing:
        mutation(None, *args)
    assert missing.value.code == "TENANT_SCOPE_REQUIRED"


def test_d2b_graph_scope_conflict_and_nested_ids_are_tenant_local() -> None:
    suffix = uuid.uuid4().hex
    scope_a = TenantScope(f"org-ga-{suffix}", f"project-ga-{suffix}")
    scope_b = TenantScope(f"org-gb-{suffix}", f"project-gb-{suffix}")
    _ensure_scope(scope_a)
    _ensure_scope(scope_b)

    shared_nested = f"node-{suffix}"
    graph_a = f"graph-a-{suffix}"
    graph_b = f"graph-b-{suffix}"
    payload_a = {
        "pipeline_id": graph_a,
        "nodes": [{"id": shared_nested, "name": "A"}],
        "edges": [],
    }
    payload_b = {
        "pipeline_id": graph_b,
        "nodes": [{"id": shared_nested, "name": "B"}],
        "edges": [],
    }
    dos.persist_phase5_pipeline_graph(scope_a, payload_a)
    dos.persist_phase5_pipeline_graph(scope_b, payload_b)

    assert dos.load_phase5_pipeline_graph(scope_a, graph_a) is not None
    assert dos.load_phase5_pipeline_graph(scope_b, graph_a) is None
    with pytest.raises(ApiError) as conflict:
        dos.persist_phase5_pipeline_graph(
            scope_b,
            {
                "pipeline_id": graph_a,
                "nodes": [{"id": f"conflict-{suffix}", "name": "conflict"}],
                "edges": [],
            },
        )
    assert conflict.value.code == "TENANT_SCOPE_CONFLICT"

    dos.delete_phase5_pipeline_graph(scope_b, graph_a)
    assert dos.load_phase5_pipeline_graph(scope_a, graph_a) is not None
    dos.delete_phase5_pipeline_graph(scope_a, graph_a)
    dos.delete_phase5_pipeline_graph(scope_b, graph_b)


def test_d2b_scoped_delete_cannot_remove_other_tenant_rows() -> None:
    suffix = uuid.uuid4().hex
    scope_a = TenantScope(f"org-da-{suffix}", f"project-da-{suffix}")
    scope_b = TenantScope(f"org-db-{suffix}", f"project-db-{suffix}")
    _ensure_scope(scope_a)
    _ensure_scope(scope_b)
    ids = {
        "source": f"source-{suffix}",
        "pipeline": f"pipeline-{suffix}",
        "dataset": f"dataset-{suffix}",
        "sync": f"sync-{suffix}",
        "schedule": f"schedule-{suffix}",
    }
    dos.persist_source(scope_a, {"id": ids["source"], "type": "file"})
    dos.persist_pipeline(
        scope_a,
        {
            "id": ids["pipeline"],
            "sourceId": ids["source"],
            "target": "dataset",
        },
    )
    dos.persist_dataset(scope_a, {"rid": ids["dataset"], "name": "D"})
    dos.persist_dataset_history(scope_a, ids["dataset"], [{"version": 1}])
    dos.persist_sync(scope_a, {"id": ids["sync"], "sourceId": ids["source"]})
    dos.persist_schedule(
        scope_a, {"id": ids["schedule"], "pipelineId": ids["pipeline"]}
    )

    dos.delete_source(scope_b, ids["source"])
    dos.delete_pipeline(scope_b, ids["pipeline"])
    dos.delete_dataset(scope_b, ids["dataset"])
    dos.delete_sync(scope_b, ids["sync"])
    dos.delete_schedule(scope_b, ids["schedule"])

    checks = {
        "meta_source": ("id", ids["source"]),
        "meta_pipeline": ("id", ids["pipeline"]),
        "meta_dataset": ("rid", ids["dataset"]),
        "meta_dataset_history": ("dataset_rid", ids["dataset"]),
        "meta_sync": ("id", ids["sync"]),
        "meta_schedule": ("id", ids["schedule"]),
    }
    with connect() as conn:
        for table, (column, value) in checks.items():
            assert conn.execute(
                f"SELECT count(*) AS n FROM {table} WHERE {column}=%s",
                (value,),
            ).fetchone()["n"] == 1

    dos.delete_source(scope_a, ids["source"])
    dos.delete_pipeline(scope_a, ids["pipeline"])
    dos.delete_dataset(scope_a, ids["dataset"])
    dos.delete_sync(scope_a, ids["sync"])
    dos.delete_schedule(scope_a, ids["schedule"])


def test_d2b_boot_never_physically_deletes_demo_rows_without_scope() -> None:
    suffix = uuid.uuid4().hex
    scope = TenantScope(f"org-boot-{suffix}", f"project-boot-{suffix}")
    _ensure_scope(scope)
    demo_id = dos.DEMO_SURFACE_IDS["sources"][0]
    with connect() as conn:
        conn.execute("DELETE FROM meta_source WHERE id=%s", (demo_id,))
        conn.commit()
    dos.persist_source(scope, {"id": demo_id, "type": "file"})
    surface = SimpleNamespace(
        _connectors={},
        _pipelines={},
        _datasets={},
        _syncs={},
        _schedules={},
        _dataset_history={},
        _dlq=[],
    )
    dos.boot_data_os(surface)
    assert demo_id not in surface._connectors
    with connect() as conn:
        row = conn.execute(
            "SELECT org_id,project_id FROM meta_source WHERE id=%s", (demo_id,)
        ).fetchone()
    assert (row["org_id"], row["project_id"]) == scope.key
    dos.delete_source(scope, demo_id)
