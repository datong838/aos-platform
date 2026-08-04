from __future__ import annotations

import importlib.util
import json
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from aos_api.db import connect, get_dsn
from aos_api.tenant_schema_lint import build_ti3_e7_schema_report
from aos_api.tenant_scope import TenantScope
from psycopg.errors import ForeignKeyViolation, InsufficientPrivilege, RaiseException

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "228ti3e7_object_runtime_contract.py"
TABLES = (
    "funnel_status",
    "graph_edge",
    "meta_branch",
    "obj_branch_overlay",
    "obj_instance",
    "object_lifecycle",
    "draft_dataset",
    "wiki_page",
    "wiki_page_version",
)


def _config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", get_dsn())
    return cfg


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


def _active_count(conn) -> int:
    return sum(
        int(conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])
        for table in TABLES
    )


def test_contract_migration_freezes_exact_boundary_and_reversibility() -> None:
    spec = importlib.util.spec_from_file_location("ti3e7_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = MIGRATION.read_text(encoding="utf-8")

    assert module.revision == "228ti3e7contract"
    assert module.down_revision == "228ti3e6rls"
    assert tuple(module.SCOPED_PRIMARY_KEYS) == TABLES
    assert "object_runtime_orphan_quarantine" in source
    assert "REVOKE ALL" in source
    assert "SET NOT NULL" in source
    assert "guard_object_runtime_quarantine_immutable" in source
    assert "FOREIGN KEY (org_id, project_id, branch_id)" in source
    assert "downgrade blocked by legacy key collision" in source


def test_e7_schema_report_is_green() -> None:
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        report = build_ti3_e7_schema_report(conn)

    assert report["ok"] is True, report
    assert report["alembicRevision"] in {
        "228ti3e7contract",
        "228ti4c1expand",
        "228ti4d1expand",
        "228ti4d4validate",
        "228ti4d6rls",
        "228ti4d7contract",
        "228ti4c3contract",
    }
    assert report["ti3ContractInvalidPrimaryKeys"] == []
    assert report["ti3ContractNullableScopeColumns"] == []
    assert report["ti3ScopedBranchForeignKeyValid"] is True
    assert report["ti3ActiveNullScopeCount"] == 0
    assert report["ti3RuntimeQuarantineAccess"] is False
    assert report["ti3QuarantineGuardTriggerCount"] == 2


def test_same_object_runtime_ids_coexist_and_branch_fk_is_scoped() -> None:
    suffix = uuid.uuid4().hex
    scope_a = TenantScope(f"org-a-{suffix}", f"project-{suffix}")
    scope_b = TenantScope(f"org-b-{suffix}", f"project-{suffix}")
    _ensure_workspace(scope_a)
    _ensure_workspace(scope_b)
    object_type = f"ContractType-{suffix}"
    object_id = f"shared-object-{suffix}"
    branch_id = f"shared-branch-{suffix}"
    only_a_branch_id = f"only-a-branch-{suffix}"
    draft_id = f"shared-draft-{suffix}"
    with connect() as conn:
        conn.execute(
            "INSERT INTO meta_object_type (id,name) VALUES (%s,%s)",
            (object_type, object_type),
        )
        for scope, owner in ((scope_a, "a"), (scope_b, "b")):
            conn.execute(
                "INSERT INTO obj_instance "
                "(object_type,object_id,props,org_id,project_id) "
                "VALUES (%s,%s,%s::jsonb,%s,%s)",
                (object_type, object_id, json.dumps({"owner": owner}), *scope.key),
            )
            conn.execute(
                "INSERT INTO meta_branch (id,name,base_ref,readonly,org_id,project_id) "
                "VALUES (%s,%s,'main',FALSE,%s,%s)",
                (branch_id, owner, *scope.key),
            )
            conn.execute(
                "INSERT INTO obj_branch_overlay "
                "(branch_id,object_type,object_id,props,org_id,project_id) "
                "VALUES (%s,%s,%s,%s::jsonb,%s,%s)",
                (branch_id, object_type, object_id, json.dumps({"owner": owner}), *scope.key),
            )
            conn.execute(
                "INSERT INTO funnel_status "
                "(object_type,stage,detail,org_id,project_id) "
                "VALUES (%s,'ingest',%s::jsonb,%s,%s)",
                (object_type, json.dumps({"owner": owner}), *scope.key),
            )
            conn.execute(
                "INSERT INTO wiki_page (object_type,object_id,body,org_id,project_id) "
                "VALUES (%s,%s,%s::jsonb,%s,%s)",
                (object_type, object_id, json.dumps({"owner": owner}), *scope.key),
            )
            conn.execute(
                "INSERT INTO draft_dataset "
                "(id,action_type_id,object_type,object_id,title,proposed,status,created_by,org_id,project_id) "
                "VALUES (%s,'contract',%s,%s,'',%s::jsonb,'proposed','test',%s,%s)",
                (draft_id, object_type, object_id, json.dumps({"owner": owner}), *scope.key),
            )
            conn.execute(
                "INSERT INTO object_lifecycle "
                "(object_type,object_id,status,reason,org_id,project_id) "
                "VALUES (%s,%s,'active','',%s,%s)",
                (object_type, object_id, *scope.key),
            )
        conn.execute(
            "INSERT INTO meta_branch (id,name,base_ref,readonly,org_id,project_id) "
            "VALUES (%s,'only-a','main',FALSE,%s,%s)",
            (only_a_branch_id, *scope_a.key),
        )
        conn.commit()

    try:
        with connect(scope_a) as conn:
            row = conn.execute(
                "SELECT props FROM obj_instance WHERE object_type=%s AND object_id=%s",
                (object_type, object_id),
            ).fetchone()
            assert row["props"]["owner"] == "a"
        with connect(scope_b) as conn:
            row = conn.execute(
                "SELECT props FROM obj_instance WHERE object_type=%s AND object_id=%s",
                (object_type, object_id),
            ).fetchone()
            assert row["props"]["owner"] == "b"
        with connect() as conn:
            with pytest.raises(ForeignKeyViolation):
                conn.execute(
                    "INSERT INTO obj_branch_overlay "
                    "(branch_id,object_type,object_id,props,org_id,project_id) "
                    "VALUES (%s,%s,%s,'{}'::jsonb,%s,%s)",
                    (
                        only_a_branch_id,
                        object_type,
                        f"cross-{suffix}",
                        *scope_b.key,
                    ),
                )
            conn.rollback()
    finally:
        with connect() as conn:
            for table in (
                "obj_branch_overlay", "object_lifecycle", "draft_dataset",
                "wiki_page", "funnel_status", "meta_branch", "obj_instance",
            ):
                conn.execute(
                    f"DELETE FROM {table} WHERE org_id IN (%s,%s) AND project_id=%s",
                    (scope_a.org_id, scope_b.org_id, scope_a.project_id),
                )
            conn.execute("DELETE FROM meta_object_type WHERE id=%s", (object_type,))
            conn.execute(
                "DELETE FROM twa_workspace WHERE org_id IN (%s,%s) AND project_id=%s",
                (scope_a.org_id, scope_b.org_id, scope_a.project_id),
            )
            conn.execute("DELETE FROM twa_org WHERE id IN (%s,%s)", (scope_a.org_id, scope_b.org_id))
            conn.commit()


def test_quarantine_is_hash_verifiable_immutable_and_runtime_inaccessible() -> None:
    with connect() as conn:
        mismatch = conn.execute(
            "SELECT COUNT(*) AS n FROM object_runtime_orphan_quarantine "
            "WHERE payload_hash <> md5(payload::text)"
        ).fetchone()["n"]
        assert mismatch == 0
        row = conn.execute(
            "SELECT quarantine_id FROM object_runtime_orphan_quarantine LIMIT 1"
        ).fetchone()
        if row:
            with pytest.raises(RaiseException):
                conn.execute(
                    "UPDATE object_runtime_orphan_quarantine SET reason_code='changed' "
                    "WHERE quarantine_id=%s",
                    (row["quarantine_id"],),
                )
            conn.rollback()
        conn.execute("SET LOCAL ROLE aos_runtime")
        with pytest.raises(InsufficientPrivilege):
            conn.execute("SELECT 1 FROM object_runtime_orphan_quarantine")
        conn.rollback()


def test_z_downgrade_upgrade_restores_and_reisolates_unknown_rows() -> None:
    cfg = _config()
    with connect() as conn:
        before_active = _active_count(conn)
        before_quarantine = int(
            conn.execute(
                "SELECT COUNT(*) AS n FROM object_runtime_orphan_quarantine"
            ).fetchone()["n"]
        )
    command.downgrade(cfg, "228ti3e6rls")
    with connect() as conn:
        assert conn.execute(
            "SELECT to_regclass('object_runtime_orphan_quarantine') AS name"
        ).fetchone()["name"] is None
        restored_active = _active_count(conn)
        restored_unknown = sum(
            int(
                conn.execute(
                    f"SELECT COUNT(*) AS n FROM {table} "
                    "WHERE org_id IS NULL OR project_id IS NULL"
                ).fetchone()["n"]
            )
            for table in TABLES
        )
        assert restored_active == before_active + before_quarantine
        assert restored_unknown == before_quarantine
    command.upgrade(cfg, "head")
    with connect() as conn:
        assert _active_count(conn) == before_active
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM object_runtime_orphan_quarantine"
        ).fetchone()["n"] == before_quarantine
