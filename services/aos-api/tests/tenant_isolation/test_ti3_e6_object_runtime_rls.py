from __future__ import annotations

import importlib.util
import json
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from psycopg.errors import InsufficientPrivilege

from aos_api.db import connect, get_dsn
from aos_api.tenant_schema_lint import build_ti3_e6_schema_report
from aos_api.tenant_scope import TenantScope

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "228ti3e6_object_runtime_rls.py"
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


def _policy_count(conn) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM pg_policies "
        "WHERE schemaname='public' AND policyname LIKE 'tenant_scope_%_ti3'"
    ).fetchone()
    return int(row["n"])


def _counts(conn) -> tuple[int, int]:
    total = unknown = 0
    for table in TABLES:
        row = conn.execute(
            f"SELECT COUNT(*) AS total, COUNT(*) FILTER "
            f"(WHERE org_id IS NULL OR project_id IS NULL) AS unknown FROM {table}"
        ).fetchone()
        total += int(row["total"])
        unknown += int(row["unknown"])
    return total, unknown


def test_migration_declares_exact_object_runtime_boundary() -> None:
    spec = importlib.util.spec_from_file_location("ti3e6_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = MIGRATION.read_text(encoding="utf-8")

    assert module.revision == "228ti3e6rls"
    assert module.down_revision == "228ti3e4validate"
    assert module.SCOPED_TABLES == TABLES
    assert "FOR ALL TO {RUNTIME_ROLE}" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "WITH CHECK" in source
    assert "CREATE ROLE" not in source
    assert "INSERT INTO" not in source
    assert "UPDATE " not in source
    assert "DELETE FROM" not in source


def test_schema_lint_confirms_nine_policies_and_safe_role() -> None:
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        report = build_ti3_e6_schema_report(conn)

    assert report["ok"] is True, report
    assert report["alembicRevision"] in {
        "228ti3e6rls",
        "228ti3e7contract",
        "228ti4c1expand",
        "228ti4d1expand",
    }
    assert report["ti3RuntimeRoleSafe"] is True
    assert report["ti3RlsTableCount"] == 9
    assert report["ti3RlsMissingTables"] == []
    assert report["ti3RlsUnprotectedTables"] == []
    assert report["ti3RuntimeOwnedTables"] == []
    assert report["ti3RlsInvalidPolicies"] == []


def test_runtime_scope_and_with_check_fail_closed() -> None:
    suffix = uuid.uuid4().hex
    scope_a = TenantScope(f"org-a-{suffix}", f"project-a-{suffix}")
    scope_b = TenantScope(f"org-b-{suffix}", f"project-b-{suffix}")
    _ensure_workspace(scope_a)
    _ensure_workspace(scope_b)
    object_type = f"RlsType-{suffix}"
    object_id = f"object-{suffix}"
    with connect() as conn:
        conn.execute(
            "INSERT INTO meta_object_type (id,name) VALUES (%s,%s)",
            (object_type, object_type),
        )
        conn.commit()

    with connect(scope_a) as conn:
        conn.execute(
            "INSERT INTO obj_instance "
            "(object_type,object_id,props,org_id,project_id) "
            "VALUES (%s,%s,%s::jsonb,%s,%s)",
            (object_type, object_id, json.dumps({"owner": "a"}), *scope_a.key),
        )
        conn.commit()
    with connect(scope_a) as conn:
        assert conn.execute(
            "SELECT 1 FROM obj_instance WHERE object_type=%s AND object_id=%s",
            (object_type, object_id),
        ).fetchone() is not None
    with connect(scope_b) as conn:
        assert conn.execute(
            "SELECT 1 FROM obj_instance WHERE object_type=%s AND object_id=%s",
            (object_type, object_id),
        ).fetchone() is None
    with connect(scope_a) as conn:
        with pytest.raises(InsufficientPrivilege):
            conn.execute(
                "INSERT INTO obj_instance "
                "(object_type,object_id,props,org_id,project_id) "
                "VALUES (%s,%s,'{}'::jsonb,%s,%s)",
                (object_type, f"blocked-{suffix}", *scope_b.key),
            )
        conn.rollback()
    with connect() as conn:
        conn.execute(
            "DELETE FROM obj_instance WHERE object_type=%s AND object_id=%s",
            (object_type, object_id),
        )
        conn.execute("DELETE FROM meta_object_type WHERE id=%s", (object_type,))
        conn.commit()


def test_runtime_role_without_guc_hides_quarantine_and_context_does_not_leak() -> None:
    suffix = uuid.uuid4().hex
    object_type = f"QuarantineType-{suffix}"
    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org (id,name) VALUES ('dev-org','测试组织') "
            "ON CONFLICT DO NOTHING"
        )
        conn.execute(
            "INSERT INTO twa_workspace (org_id,project_id,name) "
            "VALUES ('dev-org','dev-project','测试工作区') ON CONFLICT DO NOTHING"
        )
        conn.execute(
            "INSERT INTO meta_object_type (id,name) VALUES (%s,%s)",
            (object_type, object_type),
        )
        conn.execute(
            "INSERT INTO obj_instance "
            "(object_type,object_id,props,org_id,project_id) "
            "VALUES (%s,%s,'{}'::jsonb,'dev-org','dev-project')",
            (object_type, f"quarantine-{suffix}"),
        )
        conn.commit()
    with connect() as conn:
        conn.execute("SET LOCAL ROLE aos_runtime")
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM obj_instance WHERE object_type=%s",
            (object_type,),
        ).fetchone()["n"] == 0
        with pytest.raises(InsufficientPrivilege):
            conn.execute(
                "INSERT INTO obj_instance (object_type,object_id,props) "
                "VALUES (%s,%s,'{}'::jsonb)",
                (object_type, f"blocked-{suffix}"),
            )
        conn.rollback()
    with connect() as conn:
        row = conn.execute(
            "SELECT current_user AS role, "
            "current_setting('aos.org_id', true) AS org_id, "
            "current_setting('aos.project_id', true) AS project_id"
        ).fetchone()
    assert row["role"] != "aos_runtime"
    assert row["org_id"] in (None, "")
    assert row["project_id"] in (None, "")
    with connect() as conn:
        conn.execute("DELETE FROM obj_instance WHERE object_type=%s", (object_type,))
        conn.execute("DELETE FROM meta_object_type WHERE id=%s", (object_type,))
        conn.commit()


def test_z_downgrade_upgrade_is_policy_only_and_preserves_rows() -> None:
    cfg = _config()
    with connect() as conn:
        before = _counts(conn)
        quarantine = conn.execute(
            "SELECT COUNT(*) AS n FROM object_runtime_orphan_quarantine"
        ).fetchone()["n"]
        assert _policy_count(conn) == 9
    command.downgrade(cfg, "228ti3e4validate")
    with connect() as conn:
        assert _policy_count(conn) == 0
        after = _counts(conn)
        assert after[0] == before[0] + quarantine
        assert after[1] == before[1] + quarantine
    command.upgrade(cfg, "head")
    with connect() as conn:
        assert _policy_count(conn) == 9
        assert _counts(conn) == before
