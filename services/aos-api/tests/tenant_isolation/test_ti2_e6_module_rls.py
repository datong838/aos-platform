from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
from aos_api.db import connect
from aos_api.module_store import create_module, get_module
from aos_api.tenant_schema_lint import build_ti2_e6_schema_report
from aos_api.tenant_scope import TenantScope
from psycopg.errors import InsufficientPrivilege

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "228ti2e6_module_rls.py"


def _load_migration():
    spec = importlib.util.spec_from_file_location("ti2e6_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_declares_exact_role_and_policy_boundary() -> None:
    module = _load_migration()
    source = MIGRATION.read_text(encoding="utf-8")

    assert module.revision == "228ti2e6rls"
    assert module.down_revision == "228ti2e4validate"
    assert len(module.SCOPED_TABLES) == 10
    assert module.ORG_TABLES == ("module_organization_profile",)
    assert "NOLOGIN NOSUPERUSER" in source
    assert "NOBYPASSRLS" in source
    assert "ON ALL TABLES IN SCHEMA public" in source
    assert "ON ALL SEQUENCES IN SCHEMA public" in source
    assert source.count("ALTER DEFAULT PRIVILEGES IN SCHEMA public") == 2
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "WITH CHECK" in source
    assert "DROP ROLE" not in source


def test_schema_lint_confirms_runtime_role_and_eleven_policies() -> None:
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        report = build_ti2_e6_schema_report(conn)

    assert report["ok"] is True
    assert report["alembicRevision"] in {
        "228ti2e6rls",
        "228ti2e7contract",
        "228ti3e1expand",
        "228ti3e4validate",
        "228ti3e6rls",
        "228ti3e7contract",
            "228ti4c1expand",
            "228ti4d1expand",
            "228ti4d4validate",
            "228ti4d6rls",
            "228ti4d7contract",
            "228ti4c3contract",
            "228ti4a1apollo",
            "228ti5a1aip",
            "228ti5a2kv",
            "228ti5a3lineage",
            "228ti5b1models",
            "228ti6bcontract",
    }
    assert report["ti2RuntimeRoleSafe"] is True
    assert report["ti2RlsTableCount"] == 11
    assert report["ti2RlsMissingTables"] == []
    assert report["ti2RlsUnprotectedTables"] == []
    assert report["ti2RuntimeOwnedTables"] == []
    assert report["ti2RlsInvalidPolicies"] == []


def test_runtime_role_is_scope_bound_and_with_check_fails_closed() -> None:
    suffix = uuid.uuid4().hex
    scope_a = TenantScope(f"org-a-{suffix}", f"project-a-{suffix}")
    scope_b = TenantScope(f"org-b-{suffix}", f"project-b-{suffix}")
    module_id = f"module-{suffix}"

    create_module(scope_a, {"id": module_id, "name": "scope-a"})
    assert get_module(scope_a, module_id) is not None
    assert get_module(scope_b, module_id) is None

    with connect(scope_a) as conn:
        assert conn.execute("SELECT current_user AS name").fetchone()["name"] == "aos_runtime"
        with pytest.raises(InsufficientPrivilege):
            conn.execute(
                "INSERT INTO meta_module "
                "(id,name,status,description,object_type,markings,entry_path,"
                "widgets,components,buddy_bound,org_id,project_id,category,theme,"
                "module_pk,module_id) "
                "VALUES (%s,'blocked','draft','','Object','[]'::jsonb,'/',"
                "'[]'::jsonb,'{}'::jsonb,false,%s,%s,'test','light',%s,%s)",
                (
                    f"blocked-{suffix}",
                    *scope_b.key,
                    uuid.uuid4(),
                    f"blocked-{suffix}",
                ),
            )
        conn.rollback()


def test_runtime_role_without_guc_sees_nothing_and_context_does_not_leak() -> None:
    with connect() as conn:
        conn.execute("SET LOCAL ROLE aos_runtime")
        count = conn.execute("SELECT COUNT(*) AS n FROM meta_module").fetchone()["n"]
        assert count == 0

    with connect() as conn:
        row = conn.execute(
            "SELECT current_user AS role, "
            "current_setting('aos.org_id', true) AS org_id, "
            "current_setting('aos.project_id', true) AS project_id"
        ).fetchone()
        assert row["role"] != "aos_runtime"
        assert row["org_id"] in (None, "")
        assert row["project_id"] in (None, "")
