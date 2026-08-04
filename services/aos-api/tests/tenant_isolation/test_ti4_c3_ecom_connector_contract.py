from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from aos_api.db import connect, get_dsn
from aos_api.tenant_schema_lint import build_ti4_c3_schema_report
from aos_api.tenant_scope import TenantScope
from psycopg.errors import InsufficientPrivilege

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "228ti4c3_ecom_connector_contract.py"
TABLES = (
    "ecom_ingest_receipt",
    "ecom_link",
    "ecom_object",
    "ecom_sync_checkpoint",
    "oauth_token_store",
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


def _counts(conn) -> dict[str, int]:
    return {
        table: int(conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])
        for table in TABLES
    }


def test_c3_migration_validates_fks_and_forces_rls() -> None:
    spec = importlib.util.spec_from_file_location("ti4c3_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = MIGRATION.read_text(encoding="utf-8")

    assert module.revision == "228ti4c3contract"
    assert module.down_revision == "228ti4d7contract"
    assert tuple(module.SCOPED_TABLES) == TABLES
    assert "VALIDATE CONSTRAINT" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "TO {RUNTIME_ROLE}" in source
    assert "aos.org_id" in source and "aos.project_id" in source


def test_c3_schema_report_is_green() -> None:
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        report = build_ti4_c3_schema_report(conn)

    assert report["ok"] is True, report
    assert report["alembicRevision"] in {"228ti4c3contract", "228ti4a1apollo"}
    assert report["ti4EcomUnvalidatedWorkspaceForeignKeys"] == []
    assert report["ti4EcomRuntimeRoleSafe"] is True
    assert report["ti4EcomRlsTableCount"] == 5
    assert report["ti4EcomRlsMissingTables"] == []
    assert report["ti4EcomRlsUnprotectedTables"] == []
    assert report["ti4EcomRuntimeOwnedTables"] == []
    assert report["ti4EcomRlsInvalidPolicies"] == []


def test_c3_runtime_read_and_write_are_scope_bound() -> None:
    suffix = uuid.uuid4().hex
    scope_a = TenantScope(f"org-a-{suffix}", f"workspace-{suffix}")
    scope_b = TenantScope(f"org-b-{suffix}", f"workspace-{suffix}")
    _ensure_workspace(scope_a)
    _ensure_workspace(scope_b)
    row = (
        *scope_a.key,
        "contract-test",
        f"shop-{suffix}",
        "orders",
        f"receipt-{suffix}",
        "0" * 64,
    )
    with connect(scope_a) as conn:
        conn.execute(
            "INSERT INTO ecom_ingest_receipt "
            "(org_id,workspace_id,platform,shop_or_marketplace_id,stream,"
            "idempotency_key,request_hash,result,created_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,'{}'::jsonb,NOW())",
            row,
        )
        conn.commit()
    with connect(scope_b) as conn:
        visible = conn.execute(
            "SELECT COUNT(*) AS n FROM ecom_ingest_receipt WHERE idempotency_key=%s",
            (f"receipt-{suffix}",),
        ).fetchone()["n"]
        assert int(visible) == 0
    with connect(scope_a) as conn:
        with pytest.raises(InsufficientPrivilege):
            conn.execute(
                "INSERT INTO ecom_ingest_receipt "
                "(org_id,workspace_id,platform,shop_or_marketplace_id,stream,"
                "idempotency_key,request_hash,result,created_at) "
                "VALUES (%s,%s,'contract-test',%s,'orders',%s,%s,'{}'::jsonb,NOW())",
                (*scope_b.key, f"shop-{suffix}", f"blocked-{suffix}", "1" * 64),
            )
        conn.rollback()
    with connect() as conn:
        conn.execute(
            "DELETE FROM ecom_ingest_receipt WHERE idempotency_key=%s",
            (f"receipt-{suffix}",),
        )
        conn.commit()


def test_c3_missing_scope_is_fail_closed() -> None:
    with connect() as conn:
        conn.execute("SET LOCAL ROLE aos_runtime")
        assert (
            int(
                conn.execute(
                    "SELECT COUNT(*) AS n FROM ecom_ingest_receipt"
                ).fetchone()["n"]
            )
            == 0
        )
        with pytest.raises(InsufficientPrivilege):
            conn.execute(
                "INSERT INTO ecom_ingest_receipt "
                "(org_id,workspace_id,platform,shop_or_marketplace_id,stream,"
                "idempotency_key,request_hash,result,created_at) "
                "VALUES ('missing','missing','test','test','test','test',%s,"
                "'{}'::jsonb,NOW())",
                ("2" * 64,),
            )
        conn.rollback()


def test_z_c3_downgrade_upgrade_preserves_rows_and_restores_contract() -> None:
    cfg = _config()
    with connect() as conn:
        before = _counts(conn)
    command.downgrade(cfg, "228ti4d7contract")
    with connect() as conn:
        assert _counts(conn) == before
        validated = int(
            conn.execute(
                "SELECT COUNT(*) AS n FROM pg_constraint "
                "WHERE conname = ANY(%s) AND convalidated",
                ([f"fk_{table}_workspace_ti4" for table in TABLES],),
            ).fetchone()["n"]
        )
        protected = int(
            conn.execute(
                "SELECT COUNT(*) AS n FROM pg_class "
                "WHERE relname = ANY(%s) AND relrowsecurity",
                (list(TABLES),),
            ).fetchone()["n"]
        )
        assert validated == 0 and protected == 0
    command.upgrade(cfg, "head")
    with connect() as conn:
        assert _counts(conn) == before
        assert build_ti4_c3_schema_report(conn)["ok"] is True
