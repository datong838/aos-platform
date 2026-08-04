from __future__ import annotations

import uuid

import pytest
from aos_api.db import connect
from aos_api.object_runtime_ownership import (
    apply_plan,
    approve_plan,
    build_plan,
    persist_plan,
    rollback_plan,
    verify_plan,
)
from aos_api.tenant_dual_write import stable_key_hash


def _ensure_owner_scope(conn) -> None:
    conn.execute(
        "INSERT INTO twa_org (id,name) VALUES ('dev-org','测试组织') "
        "ON CONFLICT DO NOTHING"
    )
    conn.execute(
        "INSERT INTO twa_workspace (org_id,project_id,name) "
        "VALUES ('dev-org','dev-project','测试工作区') ON CONFLICT DO NOTHING"
    )


@pytest.mark.skip(reason="TI-3 E7 NOT NULL replaces historical NULL injection coverage")
def test_plan_quarantines_unknown_scope_and_performs_zero_business_dml() -> None:
    suffix = uuid.uuid4().hex
    object_type = f"E3Object-{suffix}"
    object_id = f"unknown-{suffix}"
    label = f"pytest-{suffix}"
    with connect() as conn:
        _ensure_owner_scope(conn)
        conn.execute(
            "INSERT INTO meta_object_type (id,name) VALUES (%s,%s)",
            (object_type, object_type),
        )
        conn.execute(
            "INSERT INTO obj_instance (object_type,object_id,props,org_id,project_id) "
            "VALUES (%s,%s,'{}'::jsonb,NULL,NULL)",
            (object_type, object_id),
        )
        plan = build_plan(conn, code_commit="5e58768", batch_label=label)
        replay = build_plan(conn, code_commit="5e58768", batch_label=label)
        assert plan["gate"] == "GREEN"
        assert plan["batchId"] == replay["batchId"]
        assert plan["decisionCounts"]["ASSIGN"] == 0
        assert plan["decisionCounts"]["QUARANTINE"] >= 1
        before = plan["sourceSnapshotHash"]

        persist_plan(
            conn,
            plan=plan,
            environment_hash=stable_key_hash(label, "environment"),
            planner_actor_hash=stable_key_hash(label, "planner"),
        )
        approve_plan(
            conn,
            batch_id=plan["batchId"],
            approver_actor_hash=stable_key_hash(label, "approver"),
        )
        applied = apply_plan(
            conn,
            batch_id=plan["batchId"],
            executor_actor_hash=stable_key_hash(label, "executor"),
        )
        assert applied["businessRowsUpdated"] == 0
        verified = verify_plan(
            conn,
            batch_id=plan["batchId"],
            verifier_actor_hash=stable_key_hash(label, "verifier"),
        )
        assert verified["gate"] == "GREEN"
        assert verified["businessRowsUpdated"] == 0
        rolled_back = rollback_plan(
            conn,
            batch_id=plan["batchId"],
            executor_actor_hash=stable_key_hash(label, "executor"),
        )
        assert rolled_back["gate"] == "GREEN"
        assert rolled_back["businessRowsUpdated"] == 0
        assert (
            build_plan(conn, code_commit="5e58768", batch_label="after")[
                "sourceSnapshotHash"
            ]
            == before
        )
        row = conn.execute(
            "SELECT org_id,project_id FROM obj_instance "
            "WHERE object_type=%s AND object_id=%s",
            (object_type, object_id),
        ).fetchone()
        assert row["org_id"] is None and row["project_id"] is None
        conn.rollback()


def test_apply_blocks_when_business_snapshot_drifts() -> None:
    suffix = uuid.uuid4().hex
    label = f"drift-{suffix}"
    with connect() as conn:
        _ensure_owner_scope(conn)
        plan = build_plan(conn, code_commit="5e58768", batch_label=label)
        persist_plan(
            conn,
            plan=plan,
            environment_hash=stable_key_hash(label, "environment"),
            planner_actor_hash=stable_key_hash(label, "planner"),
        )
        approve_plan(
            conn,
            batch_id=plan["batchId"],
            approver_actor_hash=stable_key_hash(label, "approver"),
        )
        object_type = f"Drift-{suffix}"
        conn.execute(
            "INSERT INTO meta_object_type (id,name) VALUES (%s,%s)",
            (object_type, object_type),
        )
        conn.execute(
            "INSERT INTO obj_instance (object_type,object_id,props,org_id,project_id) "
            "VALUES (%s,'new','{}'::jsonb,'dev-org','dev-project')",
            (object_type,),
        )
        with pytest.raises(RuntimeError, match="drifted"):
            apply_plan(
                conn,
                batch_id=plan["batchId"],
                executor_actor_hash=stable_key_hash(label, "executor"),
            )
        conn.rollback()
