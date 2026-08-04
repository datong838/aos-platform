from __future__ import annotations

import uuid

import pytest

from aos_api.auth import Principal
from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.routers.ontology import (
    BranchIn,
    FunnelRerunIn,
    GraphEdgeBatchIn,
    GraphEdgeIn,
    ObjectPutIn,
    create_branch,
    funnel_rerun,
    put_object,
    upsert_graph_edges,
)


def _principal(org_id: str, project_id: str) -> Principal:
    return Principal(
        subject="tenant-test",
        org_id=org_id,
        project_id=project_id,
        roles=["admin"],
        markings=["public"],
    )


def _ensure_workspace(org_id: str, project_id: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org (id,name) VALUES (%s,%s) ON CONFLICT DO NOTHING",
            (org_id, org_id),
        )
        conn.execute(
            "INSERT INTO twa_workspace (org_id,project_id,name) "
            "VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
            (org_id, project_id, project_id),
        )
        conn.commit()


def test_graph_and_funnel_new_writes_are_scoped_and_global_conflicts_fail() -> None:
    suffix = uuid.uuid4().hex
    scope_a = (f"org-a-{suffix}", f"project-{suffix}")
    scope_b = (f"org-b-{suffix}", f"project-{suffix}")
    _ensure_workspace(*scope_a)
    _ensure_workspace(*scope_b)
    edge = GraphEdgeIn(
        srcType=f"Source-{suffix}",
        srcId="same",
        rel="related",
        dstType=f"Target-{suffix}",
        dstId="same",
    )
    body = GraphEdgeBatchIn(edges=[edge])
    assert upsert_graph_edges(body, _principal(*scope_a))["ok"] is True
    with pytest.raises(ApiError) as conflict:
        upsert_graph_edges(body, _principal(*scope_b))
    assert conflict.value.status_code == 409

    object_type = f"funnel-{suffix}"
    assert funnel_rerun(
        object_type, FunnelRerunIn(mode="live"), _principal(*scope_a)
    )["stage"] == "hydration"
    with pytest.raises(ApiError) as funnel_conflict:
        funnel_rerun(
            object_type, FunnelRerunIn(mode="live"), _principal(*scope_b)
        )
    assert funnel_conflict.value.status_code == 409

    edge_values = (
        edge.srcType,
        edge.srcId,
        edge.rel,
        edge.dstType,
        edge.dstId,
    )

    with connect() as conn:
        graph_scope = conn.execute(
            "SELECT org_id,project_id FROM graph_edge "
            "WHERE src_type=%s AND src_id=%s AND rel=%s AND dst_type=%s AND dst_id=%s",
            edge_values,
        ).fetchone()
        funnel_scope = conn.execute(
            "SELECT org_id,project_id FROM funnel_status WHERE object_type=%s",
            (object_type,),
        ).fetchone()
    assert tuple(graph_scope.values()) == scope_a
    assert tuple(funnel_scope.values()) == scope_a


def test_branch_and_overlay_new_writes_inherit_principal_scope() -> None:
    suffix = uuid.uuid4().hex
    scope = (f"org-{suffix}", f"project-{suffix}")
    _ensure_workspace(*scope)
    principal = _principal(*scope)
    branch_id = f"branch-{suffix}"
    object_type = f"Object-{suffix}"
    object_id = "one"

    with connect() as conn:
        conn.execute(
            "INSERT INTO meta_object_type "
            "(id,name,description,published,properties,required_markings) "
            "VALUES (%s,%s,'',true,'[]'::jsonb,'[]'::jsonb)",
            (object_type, object_type),
        )
        conn.execute(
            "INSERT INTO obj_instance "
            "(object_type,object_id,props,org_id,project_id) "
            "VALUES (%s,%s,'{}'::jsonb,%s,%s)",
            (object_type, object_id, *scope),
        )
        conn.commit()

    created = create_branch(
        BranchIn(id=branch_id, name=branch_id, baseRef="main"), principal
    )
    assert created["id"] == branch_id
    written = put_object(
        object_type,
        object_id,
        ObjectPutIn(props={"owner": scope[0]}, op="upsert"),
        principal,
        branch_id,
    )
    assert written["ok"] is True

    with connect() as conn:
        branch_scope = conn.execute(
            "SELECT org_id,project_id FROM meta_branch WHERE id=%s", (branch_id,)
        ).fetchone()
        overlay_scope = conn.execute(
            "SELECT org_id,project_id FROM obj_branch_overlay "
            "WHERE branch_id=%s AND object_type=%s AND object_id=%s",
            (branch_id, object_type, object_id),
        ).fetchone()
    assert tuple(branch_scope.values()) == scope
    assert tuple(overlay_scope.values()) == scope
