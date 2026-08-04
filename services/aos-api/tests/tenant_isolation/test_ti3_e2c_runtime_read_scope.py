from __future__ import annotations

import ast
import inspect
import json
import re
import uuid
from pathlib import Path

import pytest
from aos_api.auth import Principal
from aos_api.branch_store import (
    change_count,
    diff_branch,
    effective_object,
    effective_objects,
)
from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.routers.object_sets import _query_pg
from aos_api.routers.ontology import funnel_status, neighbors
from aos_api.tenant_scope import TenantScope
from aos_api.tool_runtime import invoke_tool


def _principal(scope: TenantScope) -> Principal:
    return Principal(
        subject="tenant-test",
        org_id=scope.org_id,
        project_id=scope.project_id,
        roles=["admin"],
        markings=["public"],
    )


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
        conn.commit()


def test_object_graph_funnel_and_tool_reads_are_scope_isolated() -> None:
    suffix = uuid.uuid4().hex
    scope_a = TenantScope(f"org-a-{suffix}", f"project-a-{suffix}")
    scope_b = TenantScope(f"org-b-{suffix}", f"project-b-{suffix}")
    _ensure_workspace(scope_a)
    _ensure_workspace(scope_b)
    object_type = f"ReadType-{suffix}"
    source_id = f"source-{suffix}"
    with connect() as conn:
        conn.execute(
            "INSERT INTO meta_object_type (id,name) VALUES (%s,%s)",
            (object_type, object_type),
        )
        for scope, object_id in ((scope_a, "a"), (scope_b, "b")):
            conn.execute(
                "INSERT INTO obj_instance "
                "(object_type,object_id,props,org_id,project_id) "
                "VALUES (%s,%s,%s::jsonb,%s,%s)",
                (
                    object_type,
                    object_id,
                    json.dumps({"owner": scope.org_id}),
                    *scope.key,
                ),
            )
        conn.execute(
            "INSERT INTO graph_edge "
            "(src_type,src_id,rel,dst_type,dst_id,org_id,project_id) "
            "VALUES (%s,%s,'related',%s,'a',%s,%s)",
            (object_type, source_id, object_type, *scope_a.key),
        )
        conn.execute(
            "INSERT INTO funnel_status "
            "(object_type,stage,detail,org_id,project_id) "
            "VALUES (%s,'hydration','{}'::jsonb,%s,%s)",
            (object_type, *scope_a.key),
        )
        conn.commit()

    a_rows = _query_pg(
        scope=scope_a, object_type=object_type, filters=[], page=1, page_size=50
    )
    b_rows = _query_pg(
        scope=scope_b, object_type=object_type, filters=[], page=1, page_size=50
    )
    assert [row["id"] for row in a_rows["items"]] == ["a"]
    assert [row["id"] for row in b_rows["items"]] == ["b"]

    tool_a = invoke_tool(scope_a, "query.objects", {"objectType": object_type})
    tool_b = invoke_tool(scope_b, "query.objects", {"objectType": object_type})
    assert [row["id"] for row in tool_a["result"]["items"]] == ["a"]
    assert [row["id"] for row in tool_b["result"]["items"]] == ["b"]

    assert neighbors(object_type, source_id, _principal(scope_a))["items"]
    assert neighbors(object_type, source_id, _principal(scope_b))["items"] == []
    assert funnel_status(object_type, _principal(scope_a))["stage"] == "hydration"
    with pytest.raises(ApiError) as hidden:
        funnel_status(object_type, _principal(scope_b))
    assert hidden.value.status_code == 404


def test_runtime_read_stores_require_scope_and_sql_has_dual_tenant_predicate() -> None:
    for fn in (effective_objects, effective_object, change_count, diff_branch):
        assert "scope" in inspect.signature(fn).parameters
        assert (
            inspect.signature(fn).parameters["scope"].default is inspect.Parameter.empty
        )

    package = Path(__file__).resolve().parents[2] / "aos_api"
    files = (
        package / "branch_store.py",
        package / "marking.py",
        package / "retention_jobs.py",
        package / "tool_runtime.py",
        package / "routers" / "drafts.py",
        package / "routers" / "object_sets.py",
        package / "routers" / "ontology.py",
        package / "routers" / "runtime_write.py",
        package / "routers" / "wave_ext.py",
    )
    tenant_tables = (
        "obj_instance",
        "graph_edge",
        "meta_branch",
        "obj_branch_overlay",
        "funnel_status",
        "draft_dataset",
        "wiki_page",
        "object_lifecycle",
    )
    violations: list[str] = []
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            sql = " ".join(node.value.lower().split())
            if not any(table in sql for table in tenant_tables):
                continue
            if not re.match(
                r"^(select\s|insert\s+into\s|update\s|delete\s+from\s)", sql
            ):
                continue
            if "org_id" not in sql or "project_id" not in sql:
                violations.append(
                    f"{path.name}:{getattr(node, 'lineno', 0)}:{sql[:100]}"
                )
    assert violations == []

    registry = (package / "tenant_resources.yaml").read_text(encoding="utf-8")
    for blocker in (
        "ti4-connectors",
        "tenant-vector-records",
        "tenant-scheduler-jobs",
        "decision_lineage",
    ):
        assert blocker in registry
