from __future__ import annotations

import ast
import json
import re
import uuid
from pathlib import Path

import pytest
from aos_api.db import connect
from aos_api.demo.scope import TEST_SCOPE
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope
from aos_api.vector_index import _sample_workorder_docs, upsert

TARGET_TABLES = (
    "obj_instance",
    "graph_edge",
    "meta_branch",
    "obj_branch_overlay",
    "funnel_status",
    "draft_dataset",
    "wiki_page",
    "wiki_page_version",
    "object_lifecycle",
)
DEFERRED_TI4_WRITERS = {
    "connector_runtime.py",
    "mssql_connector.py",
    "mysql_connector.py",
    "pg_connector.py",
}


def _ensure_workspace(scope: TenantScope) -> None:
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
            "('WorkOrder','WorkOrder'),('Order','Order') ON CONFLICT DO NOTHING"
        )
        conn.commit()


def test_vector_auto_sample_is_scope_bound_and_requires_scope() -> None:
    suffix = uuid.uuid4().hex
    scope_a = TenantScope(f"org-a-{suffix}", f"project-a-{suffix}")
    scope_b = TenantScope(f"org-b-{suffix}", f"project-b-{suffix}")
    _ensure_workspace(scope_a)
    _ensure_workspace(scope_b)
    with connect() as conn:
        for scope, object_id in ((scope_a, f"a-{suffix}"), (scope_b, f"b-{suffix}")):
            conn.execute(
                "INSERT INTO obj_instance "
                "(object_type,object_id,props,org_id,project_id) "
                "VALUES ('WorkOrder',%s,%s::jsonb,%s,%s)",
                (object_id, json.dumps({"title": scope.org_id}), *scope.key),
            )
        conn.commit()

    assert [row["id"] for row in _sample_workorder_docs(scope_a, limit=50)] == [
        f"a-{suffix}"
    ]
    assert [row["id"] for row in _sample_workorder_docs(scope_b, limit=50)] == [
        f"b-{suffix}"
    ]
    with pytest.raises(ApiError) as missing:
        upsert(collection=f"missing-{suffix}", auto_sample=True)
    assert missing.value.code == "TENANT_SCOPE_REQUIRED"


def test_all_object_runtime_selects_are_scoped_and_ti4_defer_is_exact() -> None:
    package = Path(__file__).resolve().parents[2] / "aos_api"
    unscoped_selects: list[str] = []
    unscoped_writers: set[str] = set()
    for path in package.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            sql = " ".join(node.value.lower().split())
            if not any(re.search(rf"\b{table}\b", sql) for table in TARGET_TABLES):
                continue
            if not re.match(
                r"^(select\s|insert\s+into\s|update\s|delete\s+from\s)", sql
            ):
                continue
            if "org_id" in sql and "project_id" in sql:
                continue
            if sql.startswith("select "):
                unscoped_selects.append(f"{path.name}:{node.lineno}:{sql[:100]}")
            else:
                unscoped_writers.add(path.name)

    assert unscoped_selects == []
    assert unscoped_writers == DEFERRED_TI4_WRITERS


def test_demo_clear_keeps_other_workspace_objects_and_templates() -> None:
    from aos_api.demo.seed import clear_test_org

    suffix = uuid.uuid4().hex
    other = TenantScope(f"org-other-{suffix}", f"project-other-{suffix}")
    _ensure_workspace(TEST_SCOPE)
    _ensure_workspace(other)
    object_type = f"DemoGuard-{suffix}"
    with connect() as conn:
        conn.execute(
            "INSERT INTO meta_object_type (id,name) VALUES (%s,%s)",
            (object_type, object_type),
        )
        conn.execute(
            "INSERT INTO obj_instance "
            "(object_type,object_id,props,org_id,project_id) "
            "VALUES ('WorkOrder',%s,'{}'::jsonb,%s,%s)",
            (f"test-{suffix}", *TEST_SCOPE.key),
        )
        conn.execute(
            "INSERT INTO obj_instance "
            "(object_type,object_id,props,org_id,project_id) "
            "VALUES ('Order',%s,'{}'::jsonb,%s,%s)",
            (f"other-{suffix}", *other.key),
        )
        conn.commit()

    result = clear_test_org()
    assert result["lineage"] == "deferred:no-tenant-scope"
    with connect() as conn:
        test_row = conn.execute(
            "SELECT 1 FROM obj_instance WHERE object_id=%s AND org_id=%s AND project_id=%s",
            (f"test-{suffix}", *TEST_SCOPE.key),
        ).fetchone()
        other_row = conn.execute(
            "SELECT 1 FROM obj_instance WHERE object_id=%s AND org_id=%s AND project_id=%s",
            (f"other-{suffix}", *other.key),
        ).fetchone()
        template = conn.execute(
            "SELECT 1 FROM meta_object_type WHERE id=%s", (object_type,)
        ).fetchone()
    assert test_row is None
    assert other_row is not None
    assert template is not None
