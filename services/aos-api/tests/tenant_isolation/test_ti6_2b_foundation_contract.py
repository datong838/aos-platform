from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic import command
from alembic.config import Config
from aos_api.db import connect, get_dsn

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "alembic" / "versions" / "228ti6b_foundation_contract.py"
TABLES = ("theme", "widget_catalog", "twa_audit", "twa_invite", "twa_join_request")


def _config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", get_dsn())
    return cfg


def _fingerprints() -> dict[str, tuple[int, str]]:
    with connect() as conn:
        return {
            table: (int(row["n"]), str(row["digest"]))
            for table in TABLES
            for row in [
                conn.execute(
                    f"SELECT COUNT(*) AS n, md5(COALESCE(string_agg("
                    f"row_to_json(t)::text, '' ORDER BY row_to_json(t)::text),'')) "
                    f"AS digest FROM {table} t"
                ).fetchone()
            ]
        }


def test_ti6_2b_migration_contract_is_frozen() -> None:
    spec = importlib.util.spec_from_file_location("ti6_2b_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.revision == "228ti6bcontract"
    assert module.down_revision == "228ti5b1models"
    assert module.ALL_TABLES == TABLES


def test_ti6_2b_live_schema_has_scoped_keys_valid_fks_and_workshop_rls() -> None:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
                   ARRAY(
                     SELECT a.attname
                       FROM pg_index i
                       CROSS JOIN LATERAL unnest(i.indkey)
                         WITH ORDINALITY AS k(attnum, ordinality)
                       JOIN pg_attribute a
                         ON a.attrelid=i.indrelid AND a.attnum=k.attnum
                      WHERE i.indrelid=c.oid AND i.indisprimary
                      ORDER BY k.ordinality
                   ) AS primary_key
              FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
             WHERE n.nspname='public' AND c.relname=ANY(%s)
             ORDER BY c.relname
            """,
            (list(TABLES),),
        ).fetchall()
        fks = conn.execute(
            "SELECT conrelid::regclass::text AS table_name, convalidated "
            "FROM pg_constraint WHERE conname LIKE 'fk_%_workspace_ti6'"
        ).fetchall()

    by_name = {str(row["relname"]): row for row in rows}
    assert set(by_name) == set(TABLES)
    for table, legacy_key in {
        "theme": "id",
        "widget_catalog": "id",
        "twa_audit": "id",
        "twa_invite": "token",
        "twa_join_request": "id",
    }.items():
        assert list(by_name[table]["primary_key"]) == [
            "org_id",
            "project_id",
            legacy_key,
        ]
    assert all(by_name[table]["relforcerowsecurity"] for table in ("theme", "widget_catalog"))
    assert {str(row["table_name"]) for row in fks} == set(TABLES)
    assert all(row["convalidated"] for row in fks)


def test_z_ti6_2b_downgrade_upgrade_preserves_rows_and_hashes() -> None:
    before = _fingerprints()
    command.downgrade(_config(), "228ti5b1models")
    assert _fingerprints() == before
    command.upgrade(_config(), "head")
    assert _fingerprints() == before
