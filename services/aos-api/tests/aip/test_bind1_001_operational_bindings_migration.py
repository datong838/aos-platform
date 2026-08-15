import json
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
import psycopg
from psycopg import DatabaseError
from psycopg.rows import dict_row

from aos_api.db import connect
from tests.aip._migration_test_support import isolated_aip_migration_database

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "bind1_001_operational_bindings.py"

CAPABILITY_COLUMNS = {
    "provider_ref",
    "model_route_ref",
    "runtime_policy_ref",
    "eval_gate_ref",
    "eval_contract_ref",
    "license_evidence_refs",
    "data_dependency_refs",
    "tool_dependency_refs",
    "budget_policy_ref",
    "allow_degraded",
    "dependency_snapshot_hash",
    "operational_readiness",
    "readiness_reasons",
    "last_evaluated_at",
    "readiness_expires_at",
}

SKILL_COLUMNS = {
    "model_route_ref",
    "runtime_policy_ref",
    "eval_gate_ref",
    "dependency_snapshot_hash",
    "readiness",
    "readiness_reasons",
    "last_evaluated_at",
    "readiness_expires_at",
}


def _config() -> Config:
    config = Config(ROOT / "alembic.ini")
    config.set_main_option("script_location", str(ROOT / "alembic"))
    return config


def test_00_bind1_migration_is_single_head_additive_and_zero_backfill() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "bind1_001"' in text
    assert 'down_revision: str | Sequence[str] | None = "aip5_005"' in text
    assert "CREATE TABLE" not in text
    assert "INSERT INTO" not in text
    assert "UPDATE aip_" not in text
    assert "DELETE FROM" not in text
    assert "BIND1_DOWNGRADE_REQUIRES_EMPTY_BINDINGS" in text
    command.upgrade(_config(), "head")


def test_bind1_columns_are_blocked_safe_and_existing_rls_is_preserved() -> None:
    with connect() as conn:
        columns = conn.execute(
            """SELECT table_name,column_name,column_default,is_nullable
               FROM information_schema.columns
               WHERE table_schema='public'
                 AND table_name IN ('aip_capability_binding','aip_skill_binding')"""
        ).fetchall()
        by_table: dict[str, dict[str, dict[str, str | None]]] = {}
        for row in columns:
            by_table.setdefault(str(row["table_name"]), {})[str(row["column_name"])] = row
        assert CAPABILITY_COLUMNS <= set(by_table["aip_capability_binding"])
        assert SKILL_COLUMNS <= set(by_table["aip_skill_binding"])
        assert "unknown" in str(
            by_table["aip_capability_binding"]["operational_readiness"]["column_default"]
        )
        assert "BINDING_NOT_EVALUATED" in str(
            by_table["aip_capability_binding"]["readiness_reasons"]["column_default"]
        )
        assert "unknown" in str(
            by_table["aip_skill_binding"]["readiness"]["column_default"]
        )

        rls = conn.execute(
            """SELECT relname,relrowsecurity,relforcerowsecurity
               FROM pg_class WHERE relname IN
                 ('aip_capability_binding','aip_skill_binding')"""
        ).fetchall()
        assert {row["relname"] for row in rls} == {
            "aip_capability_binding",
            "aip_skill_binding",
        }
        assert all(row["relrowsecurity"] and row["relforcerowsecurity"] for row in rls)
        conn.rollback()


def test_bind1_legacy_capability_binding_defaults_fail_closed() -> None:
    suffix = uuid4().hex[:10]
    org_id = f"pytest-bind1-{suffix}"
    project_id = f"pytest-bind1-project-{suffix}"
    with connect() as conn:
        conn.execute("INSERT INTO twa_org(id,name) VALUES (%s,%s)", (org_id, org_id))
        conn.execute(
            "INSERT INTO twa_workspace(org_id,project_id,name) VALUES (%s,%s,%s)",
            (org_id, project_id, project_id),
        )
        conn.execute(
            """INSERT INTO aip_capability_binding
               (org_id,project_id,binding_id,capability_ref,secret_ref,health,
                network_policy_revision,quota_policy_revision,timeout_ms,
                max_concurrency,status,version)
               VALUES (%s,%s,'binding-1',%s::jsonb,'secret://pytest/provider',
                'unknown','network-1','quota-1',30000,1,'provisioning',1)""",
            (
                org_id,
                project_id,
                json.dumps(
                    {
                        "assetType": "CapabilityRevision",
                        "assetId": "material.collect",
                        "revision": 1,
                        "contentHash": "a" * 64,
                    }
                ),
            ),
        )
        row = conn.execute(
            """SELECT operational_readiness,readiness_reasons,
                      dependency_snapshot_hash,provider_ref
               FROM aip_capability_binding
               WHERE org_id=%s AND project_id=%s AND binding_id='binding-1'""",
            (org_id, project_id),
        ).fetchone()
        assert row["operational_readiness"] == "unknown"
        assert row["readiness_reasons"] == ["BINDING_NOT_EVALUATED"]
        assert row["dependency_snapshot_hash"] is None
        assert row["provider_ref"] is None

        conn.execute("SAVEPOINT invalid_provider_ref")
        with pytest.raises(DatabaseError):
            conn.execute(
                """UPDATE aip_capability_binding
                   SET provider_ref='{"assetType":"Provider"}'::jsonb
                   WHERE org_id=%s AND project_id=%s AND binding_id='binding-1'""",
                (org_id, project_id),
            )
        conn.execute("ROLLBACK TO SAVEPOINT invalid_provider_ref")
        conn.execute("RELEASE SAVEPOINT invalid_provider_ref")
        conn.rollback()


def test_z_bind1_empty_downgrade_upgrade_is_reversible_and_single_head() -> None:
    with isolated_aip_migration_database("bind1_migration") as (config, database_url):
        command.downgrade(config, "aip5_005")
        with psycopg.connect(database_url, row_factory=dict_row) as conn:
            names = conn.execute(
                """SELECT table_name,column_name FROM information_schema.columns
                   WHERE table_schema='public'
                     AND table_name IN ('aip_capability_binding','aip_skill_binding')"""
            ).fetchall()
            by_table: dict[str, set[str]] = {}
            for row in names:
                by_table.setdefault(str(row["table_name"]), set()).add(
                    str(row["column_name"])
                )
            assert not (CAPABILITY_COLUMNS & by_table["aip_capability_binding"])
            assert not (SKILL_COLUMNS & by_table["aip_skill_binding"])
        command.upgrade(config, "head")
        with psycopg.connect(database_url, row_factory=dict_row) as conn:
            restored = conn.execute(
                """SELECT table_name,column_name FROM information_schema.columns
                   WHERE table_schema='public'
                     AND table_name IN ('aip_capability_binding','aip_skill_binding')"""
            ).fetchall()
            by_table = {}
            for row in restored:
                by_table.setdefault(str(row["table_name"]), set()).add(
                    str(row["column_name"])
                )
            assert CAPABILITY_COLUMNS <= by_table["aip_capability_binding"]
            assert SKILL_COLUMNS <= by_table["aip_skill_binding"]
