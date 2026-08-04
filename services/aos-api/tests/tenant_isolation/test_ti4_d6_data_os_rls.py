from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from aos_api.db import connect, get_dsn
from aos_api.tenant_scope import TenantScope
from psycopg.errors import InsufficientPrivilege

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "228ti4d6_data_os_rls.py"
TABLES = (
    "meta_dataset",
    "meta_dataset_history",
    "meta_pipeline",
    "meta_sync",
    "phase5_pipeline_graph",
    "meta_schedule",
    "meta_source",
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


def _policy_state(conn) -> tuple[int, int, int]:
    policy_count = int(
        conn.execute(
            "SELECT COUNT(*) AS n FROM pg_policies "
            "WHERE schemaname='public' AND policyname LIKE 'tenant_scope_%_ti4'"
        ).fetchone()["n"]
    )
    row = conn.execute(
        "SELECT COUNT(*) FILTER (WHERE relrowsecurity) AS enabled, "
        "COUNT(*) FILTER (WHERE relforcerowsecurity) AS forced "
        "FROM pg_class WHERE relnamespace='public'::regnamespace "
        "AND relname=ANY(%s)",
        (list(TABLES),),
    ).fetchone()
    return policy_count, int(row["enabled"]), int(row["forced"])


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


def test_d6_migration_declares_exact_data_os_boundary() -> None:
    spec = importlib.util.spec_from_file_location("ti4d6_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = MIGRATION.read_text(encoding="utf-8")
    assert module.revision == "228ti4d6rls"
    assert module.down_revision == "228ti4d4validate"
    assert module.SCOPED_TABLES == TABLES
    assert "FOR ALL TO {RUNTIME_ROLE}" in source
    assert "WITH CHECK" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "CREATE ROLE" not in source
    assert "INSERT INTO" not in source
    assert "UPDATE " not in source
    assert "DELETE FROM" not in source


def test_d6_runtime_scope_with_check_and_no_guc_fail_closed() -> None:
    suffix = uuid.uuid4().hex
    scope_a = TenantScope(f"org-a-{suffix}", f"project-a-{suffix}")
    scope_b = TenantScope(f"org-b-{suffix}", f"project-b-{suffix}")
    _ensure_workspace(scope_a)
    _ensure_workspace(scope_b)
    source_id = f"source-{suffix}"
    with connect(scope_a) as conn:
        conn.execute(
            "INSERT INTO meta_source (id,type,org_id,project_id) VALUES (%s,'file',%s,%s)",
            (source_id, *scope_a.key),
        )
        conn.commit()
    with connect(scope_a) as conn:
        assert conn.execute(
            "SELECT 1 FROM meta_source WHERE id=%s", (source_id,)
        ).fetchone() is not None
    with connect(scope_b) as conn:
        assert conn.execute(
            "SELECT 1 FROM meta_source WHERE id=%s", (source_id,)
        ).fetchone() is None
    with connect(scope_a) as conn:
        with pytest.raises(InsufficientPrivilege):
            conn.execute(
                "INSERT INTO meta_source (id,type,org_id,project_id) "
                "VALUES (%s,'file',%s,%s)",
                (f"blocked-{suffix}", *scope_b.key),
            )
        conn.rollback()
    with connect() as conn:
        conn.execute("SET LOCAL ROLE aos_runtime")
        assert conn.execute("SELECT COUNT(*) AS n FROM meta_source").fetchone()["n"] == 0
        with pytest.raises(InsufficientPrivilege):
            conn.execute(
                "INSERT INTO meta_source (id,type,org_id,project_id) "
                "VALUES (%s,'file',%s,%s)",
                (f"noguc-{suffix}", *scope_a.key),
            )
        conn.rollback()
    with connect() as conn:
        conn.execute("DELETE FROM meta_source WHERE id=%s", (source_id,))
        conn.commit()


def test_z_d6_downgrade_upgrade_is_policy_only_and_preserves_rows() -> None:
    cfg = _config()
    with connect() as conn:
        before = _counts(conn)
        assert _policy_state(conn) == (7, 7, 7)
    command.downgrade(cfg, "228ti4d4validate")
    with connect() as conn:
        assert _policy_state(conn) == (0, 0, 0)
        assert _counts(conn) == before
    command.upgrade(cfg, "228ti4d6rls")
    with connect() as conn:
        assert _policy_state(conn) == (7, 7, 7)
        assert _counts(conn) == before
    command.upgrade(cfg, "head")
