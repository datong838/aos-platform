"""Disposable PostgreSQL proof of the consumer boundary; no live authority."""
from contextlib import contextmanager
import importlib.util
import os
from pathlib import Path
import uuid

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import pytest

from aos_api.db import connect, get_dsn
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
CALLER = "aos_network_consumer_call"
OWNER = "aos_network_consumer_owner"
ISSUER = "aos_network_approval_issuer"


@contextmanager
def isolated_owner():
    assert os.environ.get("AOS_TEST_USE_SHARED_DATABASE") != "1"
    with psycopg.connect(get_dsn(), row_factory=dict_row) as conn:
        assert conn.info.dbname.startswith("aos_test_") and conn.info.dbname.endswith("_ti4_test")
        yield conn


def _receipt(conn, operation):
    key = "bg00ei-" + uuid.uuid4().hex
    conn.execute(
        "INSERT INTO aip_network_policy_receipt(org_id,project_id,receipt_id,operation,"
        "idempotency_key,request_hash,result_ref,created_by) VALUES(%s,%s,%s,%s,%s,%s,'{}','isolated-test')",
        (*SCOPE.key, key, operation, key, "a" * 64),
    )


def test_consumer_roles_are_nonprivileged_sealed_and_have_no_table_write_access():
    with isolated_owner() as conn:
        rows = conn.execute(
            "SELECT rolname,rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,"
            "rolreplication,rolbypassrls FROM pg_roles WHERE rolname=ANY(%s)", ([CALLER, OWNER],),
        ).fetchall()
        assert {row["rolname"] for row in rows} == {CALLER, OWNER}
        for row in rows:
            assert all(value is False for key, value in row.items() if key != "rolname")
            assert conn.execute(
                "SELECT count(*) AS n FROM pg_auth_members WHERE roleid=%s::regrole OR member=%s::regrole",
                (row["rolname"], row["rolname"]),
            ).fetchone()["n"] == 0
            assert conn.execute("SELECT count(*) AS n FROM pg_class WHERE relowner=%s::regrole",
                                (row["rolname"],)).fetchone()["n"] == 0
            for table in ("aip_action_approval_event", "aip_network_policy_head",
                          "aip_network_policy_revision", "aip_network_policy_receipt"):
                assert not conn.execute("SELECT has_table_privilege(%s,%s,'INSERT,UPDATE,DELETE') AS allowed",
                                        (row["rolname"], table)).fetchone()["allowed"]


@pytest.mark.parametrize("target", [OWNER, ISSUER, "aos_runtime"])
def test_consumer_caller_cannot_assume_another_authority(target):
    with isolated_owner() as conn:
        conn.execute(sql.SQL("SET SESSION AUTHORIZATION {}").format(sql.Identifier(CALLER)))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(target)))
        conn.rollback()


@pytest.mark.parametrize("issuer", [False, True])
def test_runtime_and_issuer_cannot_forge_activation_receipt(issuer):
    with isolated_owner() as conn:
        if issuer:
            conn.execute(sql.SQL("SET SESSION AUTHORIZATION {}").format(sql.Identifier(ISSUER)))
        conn.execute("SET LOCAL ROLE aos_runtime")
        conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", SCOPE.key)
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match="NETWORK_CONSUMER_IDENTITY_REQUIRED"):
            _receipt(conn, "network_policy.activate")
        conn.rollback()


def test_regular_publish_receipt_still_works():
    with isolated_owner():
        with connect(SCOPE) as conn:
            before = conn.execute("SELECT count(*) AS n FROM aip_network_policy_receipt").fetchone()["n"]
            _receipt(conn, "network_policy.publish")
            assert conn.execute("SELECT count(*) AS n FROM aip_network_policy_receipt").fetchone()["n"] == before+1
            conn.rollback()


def test_active_policy_insert_remains_denied():
    with isolated_owner():
        with connect(SCOPE) as conn:
            policy = "bg00ei-" + uuid.uuid4().hex
            conn.execute("INSERT INTO aip_network_policy_head(org_id,project_id,policy_id,current_revision,version) "
                         "VALUES(%s,%s,%s,1,1)", (*SCOPE.key, policy))
            with pytest.raises(psycopg.errors.CheckViolation, match="NETWORK_ACTIVATION_CONSUMPTION_REQUIRED"):
                conn.execute("INSERT INTO aip_network_policy_revision(org_id,project_id,policy_id,revision,"
                             "content_hash,lifecycle,effective_from,effective_until,payload,created_by) "
                             "VALUES(%s,%s,%s,1,%s,'active',now(),now()+interval '1 hour','{}','isolated-test')",
                             (*SCOPE.key, policy, "a" * 64))
            conn.rollback()


@pytest.mark.parametrize("mutation,reason", [
    ("ALTER ROLE aos_network_consumer_call LOGIN", "ROLE_DRIFT"),
    ("GRANT aos_runtime TO aos_network_consumer_owner", "MEMBERSHIP_DRIFT"),
    ("GRANT aos_network_consumer_owner TO aos_runtime", "MEMBERSHIP_DRIFT"),
    ("GRANT SELECT ON aip_network_policy_receipt TO aos_network_consumer_call", "OBJECT_PRIVILEGE_DRIFT"),
])
def test_migration_rejects_existing_role_drift_without_repair(mutation, reason):
    path = Path(__file__).resolve().parents[2] / "alembic/versions/a0v_119_network_consumer_boundary.py"
    spec = importlib.util.spec_from_file_location("network_consumer_boundary", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with isolated_owner() as conn:
        conn.execute(mutation)
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match=reason):
            conn.execute(migration.ROLE_BOUNDARY_SQL)
        conn.rollback()
