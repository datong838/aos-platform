from __future__ import annotations

import uuid

import pytest
from aos_api.data_os_ownership import (
    apply_plan,
    approve_plan,
    build_plan,
    persist_plan,
    rollback_plan,
    verify_plan,
)
from aos_api.db import connect
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


def _skip_after_d3_contract() -> None:
    with connect() as conn:
        revision = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    if revision and revision["version_num"] in {
        "228ti4d7contract",
        "228ti4c3contract",
    }:
        pytest.skip("D7 forbids new NULL-scope active rows; D3 history is frozen")


def test_d3_plan_is_deterministic_and_quarantines_unproven_rows() -> None:
    _skip_after_d3_contract()
    suffix = uuid.uuid4().hex
    with connect() as conn:
        _ensure_owner_scope(conn)
        conn.execute(
            "INSERT INTO meta_source (id,type,org_id,project_id) "
            "VALUES (%s,'file','dev-org','dev-project')",
            (f"source-{suffix}",),
        )
        conn.execute(
            "INSERT INTO meta_sync (id,source_id,org_id,project_id) "
            "VALUES (%s,%s,NULL,NULL)",
            (f"sync-{suffix}", f"source-{suffix}"),
        )
        conn.execute(
            "INSERT INTO meta_pipeline (id,source_id,org_id,project_id) "
            "VALUES (%s,%s,'dev-org','dev-project')",
            (f"pipeline-{suffix}", f"missing-source-{suffix}"),
        )
        first = build_plan(conn, code_commit="7a05bd8", batch_label=suffix)
        second = build_plan(conn, code_commit="7a05bd8", batch_label=suffix)
        assert first["batchId"] == second["batchId"]
        assert first["sourceSnapshotHash"] == second["sourceSnapshotHash"]
        assert first["decisionCounts"]["ASSIGN"] == 0
        assert first["decisionCounts"]["BLOCKED"] == 0
        assert first["decisionCounts"]["NO_ACTION"] >= 1
        assert first["decisionCounts"]["QUARANTINE"] >= 2
        assert sum(first["decisionCounts"].values()) == sum(
            item["total"] for item in first["tableCounts"].values()
        )
        reasons = {item["reasonCode"] for item in first["decisions"]}
        assert "TENANT_SCOPE_UNPROVEN" in reasons
        assert "PARENT_SCOPE_UNPROVEN" in reasons
        conn.rollback()


def test_d3_role_separated_zero_dml_lifecycle() -> None:
    _skip_after_d3_contract()
    suffix = uuid.uuid4().hex
    with connect() as conn:
        _ensure_owner_scope(conn)
        conn.execute(
            "INSERT INTO meta_sync (id,source_id,org_id,project_id) "
            "VALUES (%s,'unknown',NULL,NULL)",
            (f"sync-{suffix}",),
        )
        plan = build_plan(conn, code_commit="7a05bd8", batch_label=suffix)
        before = plan["sourceSnapshotHash"]
        persisted = persist_plan(
            conn,
            plan=plan,
            environment_hash=stable_key_hash(suffix, "environment"),
            planner_actor_hash=stable_key_hash(suffix, "planner"),
        )
        assert persisted["replayed"] is False
        assert persist_plan(
            conn,
            plan=plan,
            environment_hash=stable_key_hash(suffix, "environment"),
            planner_actor_hash=stable_key_hash(suffix, "planner"),
        )["replayed"] is True
        with pytest.raises(RuntimeError, match="distinct actors"):
            approve_plan(
                conn,
                batch_id=plan["batchId"],
                approver_actor_hash=stable_key_hash(suffix, "planner"),
            )
        approve_plan(
            conn,
            batch_id=plan["batchId"],
            approver_actor_hash=stable_key_hash(suffix, "approver"),
        )
        applied = apply_plan(
            conn,
            batch_id=plan["batchId"],
            executor_actor_hash=stable_key_hash(suffix, "executor"),
        )
        assert applied["businessRowsUpdated"] == 0
        assert apply_plan(
            conn,
            batch_id=plan["batchId"],
            executor_actor_hash=stable_key_hash(suffix, "executor-2"),
        )["replayed"] is True
        verified = verify_plan(
            conn,
            batch_id=plan["batchId"],
            verifier_actor_hash=stable_key_hash(suffix, "verifier"),
        )
        assert verified["gate"] == "GREEN"
        assert verified["businessRowsUpdated"] == 0
        assert rollback_plan(
            conn,
            batch_id=plan["batchId"],
            executor_actor_hash=stable_key_hash(suffix, "executor"),
        )["gate"] == "GREEN"
        assert build_plan(conn, code_commit="7a05bd8", batch_label="after")[
            "sourceSnapshotHash"
        ] == before
        conn.rollback()


def test_d3_apply_blocks_on_business_snapshot_drift() -> None:
    _skip_after_d3_contract()
    suffix = uuid.uuid4().hex
    with connect() as conn:
        _ensure_owner_scope(conn)
        plan = build_plan(conn, code_commit="7a05bd8", batch_label=suffix)
        persist_plan(
            conn,
            plan=plan,
            environment_hash=stable_key_hash(suffix, "environment"),
            planner_actor_hash=stable_key_hash(suffix, "planner"),
        )
        approve_plan(
            conn,
            batch_id=plan["batchId"],
            approver_actor_hash=stable_key_hash(suffix, "approver"),
        )
        conn.execute(
            "INSERT INTO phase5_pipeline_graph (pipeline_id,payload) "
            "VALUES (%s,'{}'::jsonb)",
            (f"graph-{suffix}",),
        )
        with pytest.raises(RuntimeError, match="drifted"):
            apply_plan(
                conn,
                batch_id=plan["batchId"],
                executor_actor_hash=stable_key_hash(suffix, "executor"),
            )
        conn.rollback()
