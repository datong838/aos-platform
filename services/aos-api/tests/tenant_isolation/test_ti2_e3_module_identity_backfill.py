from __future__ import annotations

import uuid

import pytest

from aos_api.canvas_config import put_config
from aos_api.db import connect
from aos_api.module_deployments import deploy
from aos_api.module_events import create_event
from aos_api.module_identity_backfill import (
    apply_plan,
    approve_plan,
    build_plan,
    persist_plan,
    rollback_plan,
    stable_module_pk,
    verify_plan,
)
from aos_api.module_interfaces import put_interface
from aos_api.module_queries import create_query
from aos_api.module_store import create_module
from aos_api.module_variables import create_variable
from aos_api.tenant_dual_write import stable_key_hash
from aos_api.tenant_scope import TenantScope
from aos_api.widget_instances import create_instance


def _e7_contract_is_active() -> bool:
    with connect() as conn:
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    return bool(row and row["version_num"] == "228ti2e7contract")


def test_stable_module_pk_is_deterministic_and_scope_sensitive() -> None:
    first = stable_module_pk("org-a", "ws-a", "orders")
    assert first == stable_module_pk("org-a", "ws-a", "orders")
    assert first != stable_module_pk("org-b", "ws-a", "orders")
    assert first != stable_module_pk("org-a", "ws-b", "orders")


def test_plan_apply_verify_and_rollback_are_lossless(client) -> None:
    if _e7_contract_is_active():
        pytest.skip("E3 nullable backfill drill is superseded by the E7 NOT NULL contract")
    label = f"pytest-{uuid.uuid4().hex}"
    planner = stable_key_hash(label, "planner")
    approver = stable_key_hash(label, "approver")
    executor = stable_key_hash(label, "executor")
    verifier = stable_key_hash(label, "verifier")
    environment_hash = stable_key_hash(label, "environment")

    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org (id, name) VALUES ('dev-org', '测试组织') "
            "ON CONFLICT (id) DO NOTHING"
        )
        conn.execute(
            "INSERT INTO twa_workspace (org_id, project_id, name) "
            "VALUES ('dev-org', 'dev-project', '默认工作区') "
            "ON CONFLICT (org_id, project_id) DO NOTHING"
        )
        parent = conn.execute(
            "SELECT id, org_id, project_id FROM meta_module ORDER BY id LIMIT 1"
        ).fetchone()
        assert parent is not None
        child_id = f"e3-child-{uuid.uuid4().hex}"
        conn.execute(
            "INSERT INTO module_events (id, module_id, name, org_id, project_id) "
            "VALUES (%s,%s,'linked',%s,%s)",
            (child_id, parent["id"], parent["org_id"], parent["project_id"]),
        )
        before_counts = _identity_counts(conn)
        plan = build_plan(conn, code_commit="472728e", batch_label=label)
        replay = build_plan(conn, code_commit="472728e", batch_label=label)
        assert plan["gate"] == "GREEN"
        assert plan["batchId"] == replay["batchId"]
        assert plan["decisionCounts"]["ASSIGN"] > 0
        assert plan["scopeCounts"].get("org-org/dev-project", 0) == 0

        persisted = persist_plan(
            conn,
            plan=plan,
            environment_hash=environment_hash,
            planner_actor_hash=planner,
        )
        assert persisted["replayed"] is False
        approve_plan(conn, batch_id=plan["batchId"], approver_actor_hash=approver)
        applied = apply_plan(
            conn, batch_id=plan["batchId"], executor_actor_hash=executor
        )
        assert applied["gate"] == "GREEN"
        assert applied["applied"] == plan["decisionCounts"]["ASSIGN"]
        verified = verify_plan(
            conn, batch_id=plan["batchId"], verifier_actor_hash=verifier
        )
        assert verified == {
            "batchId": plan["batchId"],
            "gate": "GREEN",
            "verified": applied["applied"],
        }
        after_counts = _identity_counts(conn)
        for table, before in before_counts.items():
            assigned = sum(
                1
                for item in plan["decisions"]
                if item["decision"] == "ASSIGN" and item["resource"] == table
            )
            assert after_counts[table] == before + assigned

        rolled_back = rollback_plan(
            conn, batch_id=plan["batchId"], executor_actor_hash=executor
        )
        assert rolled_back["gate"] == "GREEN"
        assert rolled_back["rolledBack"] == applied["applied"]
        assert _identity_counts(conn) == before_counts
        conn.commit()


def test_plan_quarantines_orphan_and_blocks_conflicting_identity(client) -> None:
    if _e7_contract_is_active():
        pytest.skip("E3 orphan injection is rejected by the E7 NOT NULL contract")
    label = f"negative-{uuid.uuid4().hex}"
    scope = TenantScope(f"org-{label}", f"project-{label}")
    module_id = f"module-{uuid.uuid4().hex}"
    create_module(scope, {"id": module_id, "name": "identity-conflict"})
    with connect() as conn:
        parent = conn.execute(
            "SELECT id, org_id, project_id FROM meta_module "
            "WHERE id=%s AND org_id=%s AND project_id=%s",
            (module_id, *scope.key),
        ).fetchone()
        assert parent is not None
        conn.execute(
            "UPDATE meta_module SET module_pk=%s WHERE id=%s",
            (uuid.uuid4(), parent["id"]),
        )
        orphan_id = f"orphan-{uuid.uuid4().hex}"
        conn.execute(
            "INSERT INTO module_events (id, module_id, name, org_id, project_id) "
            "VALUES (%s,%s,'orphan',%s,%s)",
            (orphan_id, "missing-parent", parent["org_id"], parent["project_id"]),
        )

        plan = build_plan(conn, code_commit="472728e", batch_label=label)

        assert plan["gate"] == "BLOCKED"
        assert plan["decisionCounts"]["BLOCKED"] >= 1
        assert plan["decisionCounts"]["QUARANTINE"] >= 1
        with pytest.raises(RuntimeError, match="blocked"):
            persist_plan(
                conn,
                plan=plan,
                environment_hash=stable_key_hash(label, "environment"),
                planner_actor_hash=stable_key_hash(label, "planner"),
            )
        conn.rollback()


def test_new_module_and_children_inherit_stable_module_pk(client) -> None:
    suffix = uuid.uuid4().hex
    scope = TenantScope(f"org-new-{suffix}", f"ws-new-{suffix}")
    module = create_module(scope, {"name": "orders"})
    module_id = module["id"]

    put_config(scope, module_id, {}, {})
    create_instance(scope, module_id, {"title": "widget"})
    create_variable(scope, module_id, {"name": "selected"})
    create_query(scope, module_id, {"name": "orders"})
    create_event(scope, module_id, {"name": "refresh"})
    put_interface(scope, module_id, {"name": "orders-api"})
    deploy(scope, module_id, "dev")

    expected = stable_module_pk(*scope.key, module_id)
    with connect() as conn:
        parent = conn.execute(
            "SELECT module_pk, module_id FROM meta_module "
            "WHERE id=%s AND org_id=%s AND project_id=%s",
            (module_id, *scope.key),
        ).fetchone()
        assert parent is not None
        assert parent["module_pk"] == expected
        assert parent["module_id"] == module_id
        for table in (
            "module_canvas_config",
            "module_deployment",
            "module_events",
            "module_interface",
            "module_query",
            "module_variable",
            "module_widget_instance",
        ):
            rows = conn.execute(
                f"SELECT module_pk FROM {table} "
                "WHERE module_id=%s AND org_id=%s AND project_id=%s",
                (module_id, *scope.key),
            ).fetchall()
            assert rows, table
            assert {row["module_pk"] for row in rows} == {expected}, table


def _identity_counts(conn) -> dict[str, int]:
    tables = (
        "meta_module",
        "module_canvas_config",
        "module_deployment",
        "module_events",
        "module_interface",
        "module_query",
        "module_variable",
        "module_widget_instance",
    )
    return {
        table: int(
            conn.execute(
                f"SELECT COUNT(*) AS count FROM {table} WHERE module_pk IS NOT NULL"
            ).fetchone()["count"]
        )
        for table in tables
    }
