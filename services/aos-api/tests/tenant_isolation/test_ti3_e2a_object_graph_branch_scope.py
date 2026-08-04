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


def test_graph_and_funnel_same_ids_coexist_across_scopes() -> None:
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
    assert upsert_graph_edges(body, _principal(*scope_b))["ok"] is True

    object_type = f"funnel-{suffix}"
    assert funnel_rerun(
        object_type, FunnelRerunIn(mode="live"), _principal(*scope_a)
    )["stage"] == "hydration"
    assert funnel_rerun(
        object_type, FunnelRerunIn(mode="live"), _principal(*scope_b)
    )["stage"] == "hydration"

    edge_values = (
        edge.srcType,
        edge.srcId,
        edge.rel,
        edge.dstType,
        edge.dstId,
    )

    with connect() as conn:
        graph_scopes = conn.execute(
            "SELECT org_id,project_id FROM graph_edge "
            "WHERE src_type=%s AND src_id=%s AND rel=%s AND dst_type=%s AND dst_id=%s "
            "ORDER BY org_id",
            edge_values,
        ).fetchall()
        funnel_scopes = conn.execute(
            "SELECT org_id,project_id FROM funnel_status WHERE object_type=%s "
            "ORDER BY org_id",
            (object_type,),
        ).fetchall()
        conn.execute(
            "DELETE FROM graph_edge WHERE src_type=%s AND src_id=%s AND rel=%s "
            "AND dst_type=%s AND dst_id=%s",
            edge_values,
        )
        conn.execute("DELETE FROM funnel_status WHERE object_type=%s", (object_type,))
        conn.commit()
    assert {(row["org_id"], row["project_id"]) for row in graph_scopes} == {
        scope_a,
        scope_b,
    }
    assert {(row["org_id"], row["project_id"]) for row in funnel_scopes} == {
        scope_a,
        scope_b,
    }


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
