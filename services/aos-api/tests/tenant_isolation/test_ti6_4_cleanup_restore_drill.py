from __future__ import annotations

import uuid

import pytest
from aos_api.db import connect
from aos_api.tenant_cleanup import (
    DELETE_SCOPED_ROWS,
    EXTERNAL_NOT_EXECUTED,
    RETAIN_BROADER_SCOPE,
    RETAIN_IMMUTABLE_HISTORY,
    build_cleanup_impact_plan,
    run_cleanup_rollback_drill,
)
from aos_api.tenant_scope import TenantScope


def _scope(label: str) -> TenantScope:
    suffix = uuid.uuid4().hex[:12]
    return TenantScope(
        f"ti6-synthetic-{label}-{suffix}", f"ti6-synthetic-workspace-{suffix}"
    )


def _seed_theme(scope: TenantScope, theme_id: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO meta_org (id,name) VALUES (%s,%s) ON CONFLICT (id) DO NOTHING",
            (scope.org_id, scope.org_id),
        )
        conn.execute(
            "INSERT INTO twa_org (id,name) VALUES (%s,%s) ON CONFLICT (id) DO NOTHING",
            (scope.org_id, scope.org_id),
        )
        conn.execute(
            "INSERT INTO meta_workspace (org_id,project_id,name,deletable,kind) "
            "VALUES (%s,%s,%s,true,'test') ON CONFLICT (org_id,project_id) DO NOTHING",
            (*scope.key, scope.project_id),
        )
        conn.execute(
            "INSERT INTO twa_workspace (org_id,project_id,name,deletable,kind) "
            "VALUES (%s,%s,%s,true,'test') ON CONFLICT (org_id,project_id) DO NOTHING",
            (*scope.key, scope.project_id),
        )
        conn.commit()
    with connect(scope) as conn:
        conn.execute(
            "INSERT INTO theme (org_id,project_id,id,name,tokens) "
            "VALUES (%s,%s,%s,%s,'{}'::jsonb)",
            (*scope.key, theme_id, theme_id),
        )
        conn.commit()


def test_ti6_4_dry_run_is_deterministic_and_classifies_resources() -> None:
    scope = _scope("plan")
    _seed_theme(scope, "theme-plan")
    with connect(scope) as conn:
        first = build_cleanup_impact_plan(conn, scope)
        second = build_cleanup_impact_plan(conn, scope)

    assert first == second
    assert first["planHash"].startswith("sha256:")
    by_name = {item["name"]: item for item in first["resources"]}
    assert by_name["theme"]["strategy"] == DELETE_SCOPED_ROWS
    assert by_name["theme"]["rowCount"] == 1
    assert any(
        item["strategy"] == RETAIN_IMMUTABLE_HISTORY for item in first["resources"]
    )
    assert by_name["module_organization_profile"]["strategy"] == RETAIN_BROADER_SCOPE
    assert any(item["strategy"] == EXTERNAL_NOT_EXECUTED for item in first["resources"])


def test_ti6_4_apply_verify_rollback_is_exact_peer_safe_and_retryable() -> None:
    target = _scope("target")
    peer = _scope("peer")
    _seed_theme(target, "theme-target")
    _seed_theme(peer, "theme-peer")
    with connect(target) as conn:
        plan = build_cleanup_impact_plan(conn, target)
        first = run_cleanup_rollback_drill(
            conn,
            target,
            expected_plan_hash=plan["planHash"],
            peer_scopes=(peer,),
        )
        second = run_cleanup_rollback_drill(
            conn,
            target,
            expected_plan_hash=plan["planHash"],
            peer_scopes=(peer,),
        )
        target_count = conn.execute(
            "SELECT COUNT(*) AS count FROM theme WHERE org_id=%s AND project_id=%s",
            target.key,
        ).fetchone()["count"]
    with connect(peer) as conn:
        peer_count = conn.execute(
            "SELECT COUNT(*) AS count FROM theme WHERE org_id=%s AND project_id=%s",
            peer.key,
        ).fetchone()["count"]

    assert first == second
    assert first["deleted"] == {"theme": 1}
    assert first["restored"] is True
    assert target_count == 1
    assert peer_count == 1


def test_ti6_4_apply_rejects_non_synthetic_scope() -> None:
    protected = TenantScope("dev-org", "dev-project")
    with connect(protected) as conn:
        plan = build_cleanup_impact_plan(conn, protected)
        with pytest.raises(PermissionError, match="synthetic scope"):
            run_cleanup_rollback_drill(
                conn, protected, expected_plan_hash=plan["planHash"]
            )


def test_ti6_4_stale_plan_hash_fails_closed() -> None:
    scope = _scope("stale")
    _seed_theme(scope, "theme-stale")
    with connect(scope) as conn, pytest.raises(RuntimeError, match="plan changed"):
        run_cleanup_rollback_drill(conn, scope, expected_plan_hash="sha256:stale")
