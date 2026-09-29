"""ACL-faithful clone gate for the current Eval authority privilege drift."""
from __future__ import annotations

import os

import psycopg
import pytest


TABLES = (
    "aip_eval_issuer_root",
    "aip_eval_executor_identity",
    "aip_eval_authority_revocation",
    "aip_eval_execution_receipt",
)


@pytest.fixture()
def connection():
    dsn = os.getenv("AOS_BG00Z_ACL_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("ACL-faithful BG-00z clone required")
    with psycopg.connect(dsn) as conn:
        assert conn.info.dbname == "aos_bg00z_acl_20260929"
        assert conn.info.port == 5433
        conn.read_only = True
        yield conn


def test_acl_faithful_clone_is_least_privilege(connection):
    defaults = connection.execute(
        """SELECT defaclacl::text FROM pg_default_acl
           WHERE defaclrole='aos_app'::regrole
             AND defaclnamespace='public'::regnamespace
             AND defaclobjtype='r'"""
    ).fetchone()
    assert defaults is not None and "aos_runtime=arwd" in defaults[0]
    for table in TABLES:
        privileges = connection.execute(
            """SELECT has_table_privilege('aos_runtime', %s, 'SELECT'),
                      has_table_privilege('aos_runtime', %s, 'INSERT'),
                      has_table_privilege('aos_runtime', %s, 'UPDATE'),
                      has_table_privilege('aos_runtime', %s, 'DELETE'),
                      has_table_privilege('aos_runtime', %s, 'TRUNCATE')""",
            (table,) * 5,
        ).fetchone()
        assert privileges == (True, False, False, False, False)
        assert connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0


def test_acl_fix_migration_revision(connection):
    assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
        "a0v_113",
    )
