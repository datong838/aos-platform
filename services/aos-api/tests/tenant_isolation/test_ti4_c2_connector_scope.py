from __future__ import annotations

import uuid

import pytest
from aos_api import connector_runtime, mssql_connector, mysql_connector, pg_connector
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
        conn.execute(
            "INSERT INTO meta_object_type (id,name) VALUES "
            "('WorkOrder','WorkOrder') ON CONFLICT DO NOTHING"
        )
        conn.commit()


@pytest.mark.parametrize(
    "ingest",
    [mysql_connector.ingest, pg_connector.ingest, mssql_connector.ingest],
)
def test_connector_modules_fail_closed_without_tenant_scope(ingest) -> None:
    with pytest.raises(ApiError) as missing:
        ingest()
    assert missing.value.code == "TENANT_SCOPE_REQUIRED"


def test_rest_and_file_mock_keep_same_object_id_in_two_scopes(monkeypatch) -> None:
    suffix = uuid.uuid4().hex
    scope_a = TenantScope(f"org-a-{suffix}", f"project-a-{suffix}")
    scope_b = TenantScope(f"org-b-{suffix}", f"project-b-{suffix}")
    _ensure_scope(scope_a)
    _ensure_scope(scope_b)
    monkeypatch.setenv("AOS_REST_CONNECTOR_MOCK", "1")
    monkeypatch.delenv("AOS_REST_CONNECTOR_URL", raising=False)
    monkeypatch.setenv("AOS_FILE_LOCAL_MOCK", "1")
    monkeypatch.delenv("AOS_FILE_LOCAL_ROOT", raising=False)

    for scope in (scope_a, scope_b):
        rest = connector_runtime._rest_ingest(
            org_id=scope.org_id, project_id=scope.project_id
        )
        file_result = connector_runtime._file_local_ingest(
            org_id=scope.org_id, project_id=scope.project_id
        )
        assert (rest["orgId"], rest["projectId"]) == scope.key
        assert (file_result["orgId"], file_result["projectId"]) == scope.key

    with connect() as conn:
        rest_rows = conn.execute(
            "SELECT org_id,project_id FROM obj_instance "
            "WHERE object_type='WorkOrder' AND object_id='rest-mock-1' "
            "AND (org_id,project_id) IN ((%s,%s),(%s,%s)) ORDER BY org_id",
            (*scope_a.key, *scope_b.key),
        ).fetchall()
        file_rows = conn.execute(
            "SELECT org_id,project_id FROM obj_instance "
            "WHERE object_type='WorkOrder' AND object_id='file-mock-a.txt' "
            "AND (org_id,project_id) IN ((%s,%s),(%s,%s)) ORDER BY org_id",
            (*scope_a.key, *scope_b.key),
        ).fetchall()
    assert {(row["org_id"], row["project_id"]) for row in rest_rows} == {
        scope_a.key,
        scope_b.key,
    }
    assert {(row["org_id"], row["project_id"]) for row in file_rows} == {
        scope_a.key,
        scope_b.key,
    }


def test_jdbc_mock_and_sample_writes_are_scope_bound(monkeypatch) -> None:
    suffix = uuid.uuid4().hex
    scope = TenantScope(f"org-jdbc-{suffix}", f"project-jdbc-{suffix}")
    _ensure_scope(scope)

    monkeypatch.setenv("AOS_PG_CONNECTOR_MOCK", "1")
    monkeypatch.setenv("AOS_MSSQL_CONNECTOR_MOCK", "1")
    pg_result = pg_connector.ingest(scope=scope)
    ms_result = mssql_connector.ingest(scope=scope)

    monkeypatch.setattr(mysql_connector, "disabled", lambda: False)
    monkeypatch.setattr(mysql_connector, "get_settings", lambda: {"table": "synthetic"})
    monkeypatch.setattr(
        mysql_connector,
        "probe",
        lambda **_: {
            "ok": True,
            "mode": "live",
            "sample": [{"id": f"mysql-{suffix}", "title": "synthetic"}],
            "table": "synthetic",
            "tableRowCount": 1,
            "fullTable": False,
            "host": "mock",
            "database": "mock",
        },
    )
    mysql_result = mysql_connector.ingest(scope=scope)

    assert (pg_result["orgId"], pg_result["projectId"]) == scope.key
    assert (ms_result["orgId"], ms_result["projectId"]) == scope.key
    assert (mysql_result["orgId"], mysql_result["projectId"]) == scope.key
    object_ids = [
        pg_result["objectIds"][0],
        ms_result["objectIds"][0],
        mysql_result["objectIds"][0],
    ]
    with connect(scope) as conn:
        rows = conn.execute(
            "SELECT object_id FROM obj_instance WHERE org_id=%s AND project_id=%s "
            "AND object_id = ANY(%s)",
            (*scope.key, object_ids),
        ).fetchall()
    assert {row["object_id"] for row in rows} == set(object_ids)


def test_runtime_handlers_reject_missing_or_blank_scope(monkeypatch) -> None:
    monkeypatch.setenv("AOS_REST_CONNECTOR_MOCK", "1")
    with pytest.raises(ApiError) as missing:
        connector_runtime._rest_ingest()
    assert missing.value.code == "TENANT_SCOPE_REQUIRED"
    with pytest.raises(ApiError) as blank:
        connector_runtime._file_local_ingest(org_id=" ", project_id="p")
    assert blank.value.code == "TENANT_SCOPE_REQUIRED"
