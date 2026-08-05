from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from psycopg.errors import ForeignKeyViolation

from aos_api.db import connect, get_dsn
from aos_api.model_catalog import create_catalog, get_catalog
from aos_api.tenant_schema_lint import build_ti5_b1_schema_report
from aos_api.tenant_scope import TenantScope

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "228ti5b1_model_management_contract.py"


def _config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", get_dsn())
    return cfg


def _table_fingerprints() -> dict[str, tuple[int, str]]:
    tables = (
        "capacity_limits",
        "capacity_usage",
        "model_catalog",
        "model_provider",
        "model_route",
        "provider_health",
        "registered_models",
    )
    with connect() as conn:
        return {
            table: (
                int(row["n"]),
                str(row["digest"]),
            )
            for table in tables
            for row in [
                conn.execute(
                    f"SELECT COUNT(*) AS n, md5(COALESCE(string_agg("  # noqa: S608
                    f"row_to_json(t)::text, '' ORDER BY row_to_json(t)::text),'')) "
                    f"AS digest FROM {table} t"
                ).fetchone()
            ]
        }


def _workspace(scope: TenantScope) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org (id,name) VALUES (%s,%s) ON CONFLICT (id) DO NOTHING",
            (scope.org_id, scope.org_id),
        )
        conn.execute(
            "INSERT INTO twa_workspace (org_id,project_id,name) VALUES (%s,%s,%s) "
            "ON CONFLICT (org_id,project_id) DO NOTHING",
            (*scope.key, scope.project_id),
        )
        conn.commit()


def test_b1_migration_freezes_seven_table_contract() -> None:
    spec = importlib.util.spec_from_file_location("ti5b1_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = MIGRATION.read_text(encoding="utf-8")

    assert module.revision == "228ti5b1models"
    assert module.down_revision == "228ti5a3lineage"
    assert len(module.TABLES) == 7
    assert "PRIMARY KEY (org_id,project_id,id)" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "fk_provider_health_provider_ti5b1" in source
    assert "fk_registered_models_catalog_ti5b1" in source


def test_b1_schema_report_is_green() -> None:
    with connect() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        report = build_ti5_b1_schema_report(conn)

    assert report["ok"] is True, report
    assert report["alembicRevision"] == "228ti6cassets"
    assert report["ti5ModelManagementTableContractsValid"] is True
    assert report["ti5ModelManagementChildForeignKeysValid"] is True


def test_b1_same_catalog_id_isolated_and_no_scope_fails_closed() -> None:
    suffix = uuid.uuid4().hex
    scope_a = TenantScope(f"org-a-{suffix}", f"project-a-{suffix}")
    scope_b = TenantScope(f"org-b-{suffix}", f"project-b-{suffix}")
    _workspace(scope_a)
    _workspace(scope_b)
    model_id = f"mc-{suffix}"
    payload = {
        "id": model_id,
        "provider": "local",
        "model": "same-id-model",
        "displayName": "scope-a",
    }
    create_catalog(scope_a, payload)
    create_catalog(scope_b, {**payload, "displayName": "scope-b"})

    assert get_catalog(scope_a, model_id)["displayName"] == "scope-a"
    assert get_catalog(scope_b, model_id)["displayName"] == "scope-b"
    with connect() as conn:
        conn.execute("SET LOCAL ROLE aos_runtime")
        assert (
            conn.execute(
                "SELECT COUNT(*) AS n FROM model_catalog WHERE id=%s", (model_id,)
            ).fetchone()["n"]
            == 0
        )
    with connect(scope_a) as conn:
        assert (
            conn.execute(
                "UPDATE model_catalog SET display_name='cross' "
                "WHERE org_id=%s AND project_id=%s AND id=%s",
                (*scope_b.key, model_id),
            ).rowcount
            == 0
        )

    with connect(scope_a) as conn:
        conn.execute("DELETE FROM model_catalog WHERE id=%s", (model_id,))
        conn.commit()
    with connect(scope_b) as conn:
        conn.execute("DELETE FROM model_catalog WHERE id=%s", (model_id,))
        conn.commit()


def test_b1_child_parent_scope_mismatch_is_rejected() -> None:
    suffix = uuid.uuid4().hex
    scope_a = TenantScope(f"org-parent-{suffix}", f"project-parent-{suffix}")
    scope_b = TenantScope(f"org-child-{suffix}", f"project-child-{suffix}")
    _workspace(scope_a)
    _workspace(scope_b)
    provider_id = f"provider-{suffix}"
    with connect(scope_a) as conn:
        conn.execute(
            "INSERT INTO model_provider "
            "(org_id,project_id,id,name) VALUES (%s,%s,%s,'parent')",
            (*scope_a.key, provider_id),
        )
        conn.commit()

    with pytest.raises(ForeignKeyViolation), connect(scope_b) as conn:
        conn.execute(
            "INSERT INTO provider_health "
            "(org_id,project_id,id,provider_id) VALUES (%s,%s,%s,%s)",
            (*scope_b.key, f"health-{suffix}", provider_id),
        )

    with connect(scope_a) as conn:
        conn.execute("DELETE FROM model_provider WHERE id=%s", (provider_id,))
        conn.commit()


def test_z_b1_downgrade_upgrade_preserves_all_model_rows_and_hashes() -> None:
    before = _table_fingerprints()
    command.downgrade(_config(), "228ti5a3lineage")
    assert _table_fingerprints() == before
    command.upgrade(_config(), "head")
    assert _table_fingerprints() == before
    with connect() as conn:
        assert build_ti5_b1_schema_report(conn)["ok"] is True
