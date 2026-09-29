"""Isolated PostgreSQL gate for the default-empty Eval execution authority schema."""
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
    dsn = os.getenv("AOS_BG00Y_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("isolated BG-00y PostgreSQL URL required")
    with psycopg.connect(dsn) as conn:
        assert conn.info.dbname == "aos_bg00y_migration_20260929"
        assert conn.info.port == 5433
        yield conn
        conn.rollback()


def test_eval_execution_authority_starts_empty_and_is_runtime_read_only(connection):
    version = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    assert version == "a0v_112"
    for table in TABLES:
        row = connection.execute(
            """SELECT c.relrowsecurity, c.relforcerowsecurity,
                      has_table_privilege('aos_runtime', c.oid, 'SELECT'),
                      has_table_privilege('aos_runtime', c.oid, 'INSERT'),
                      has_table_privilege('aos_runtime', c.oid, 'UPDATE'),
                      has_table_privilege('aos_runtime', c.oid, 'DELETE')
               FROM pg_class c WHERE c.oid = %s::regclass""",
            (table,),
        ).fetchone()
        assert row == (True, True, True, False, False, False)
        assert connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0


def test_eval_execution_authority_has_tenant_scope_and_append_only(connection):
    for table in TABLES:
        policies = connection.execute(
            """SELECT roles, qual, with_check FROM pg_policies
               WHERE schemaname='public' AND tablename=%s""", (table,)
        ).fetchall()
        assert len(policies) == 1
        assert policies[0][0] == ["aos_runtime"]
        assert "aos.org_id" in policies[0][1]
        assert "aos.project_id" in policies[0][1]
        assert "aos.org_id" in policies[0][2]
        assert "aos.project_id" in policies[0][2]
        triggers = connection.execute(
            """SELECT tgname FROM pg_trigger
               WHERE tgrelid=%s::regclass AND NOT tgisinternal""", (table,)
        ).fetchall()
        assert len(triggers) == 2


def _seed_isolated_authority(connection):
    """Mechanism rows live only in this clone transaction and are rolled back."""
    connection.execute(
        """INSERT INTO aip_eval_issuer_root
           (org_id,project_id,issuer_id,key_id,purpose,public_key_base64,
            public_key_hash,valid_from,valid_until,owner_ref,approval_ref,source_hash)
           VALUES ('org-org','dev-project','bg00y-test-issuer','test-key',
                   'eval-execution','test-only',%s,now()-interval '1 hour',
                   now()+interval '1 hour','bg00y-test-owner','{"testOnly":true}',%s)""",
        ("a" * 64, "b" * 64),
    )
    connection.execute(
        """INSERT INTO aip_eval_executor_identity
           (org_id,project_id,identity_id,purpose,executor_ref,issuer_id,
            issuer_key_id,certificate_json,certificate_hash,public_key_base64,
            public_key_hash,valid_from,valid_until,owner_ref,approval_ref)
           VALUES ('org-org','dev-project','bg00y-test-target','target',
                   '{"testOnly":true}','bg00y-test-issuer','test-key',
                   '{"testOnly":true}',%s,'test-only',%s,
                   now()-interval '1 hour',now()+interval '1 hour',
                   'bg00y-test-owner','{"testOnly":true}')""",
        ("c" * 64, "d" * 64),
    )
    connection.execute(
        """INSERT INTO aip_eval_run
           (org_id,project_id,run_id,suite_id,suite_revision,suite_hash,
            target_ref,dataset_ref,judge_ref,status,idempotency_key,created_by)
           VALUES ('org-org','dev-project','bg00y-test-run','bg00y-test-suite',
                   1,%s,'{"testOnly":true}','{"testOnly":true}',
                   '{"testOnly":true}','queued','bg00y-test-key','bg00y-test-owner')""",
        ("e" * 64,),
    )


def _insert_test_receipt(connection, *, receipt_id: str, purpose: str = "target"):
    connection.execute(
        """INSERT INTO aip_eval_execution_receipt
           (org_id,project_id,receipt_id,run_id,case_id,purpose,identity_id,
           certificate_hash,suite_ref,executor_ref,claim_hash,input_hash,
            output_hash,actual_hash,passed,detail_code,occurred_at,signature_base64)
           VALUES ('org-org','dev-project',%s,'bg00y-test-run','case-1',%s,
                   'bg00y-test-target',%s,'{"testOnly":true}',
                   '{"testOnly":true}',%s,%s,%s,%s,%s,%s,now(),'test-only')""",
        (
            receipt_id, purpose, "c" * 64, "f" * 64, "1" * 64, "2" * 64,
            "2" * 64 if purpose == "judge" else None,
            True if purpose == "judge" else None,
            "test-only" if purpose == "judge" else None,
        ),
    )


def test_eval_receipt_replay_and_purpose_are_db_rejected(connection):
    _seed_isolated_authority(connection)
    _insert_test_receipt(connection, receipt_id="3" * 64)
    with pytest.raises(psycopg.errors.UniqueViolation):
        with connection.transaction():
            _insert_test_receipt(connection, receipt_id="4" * 64)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with connection.transaction():
            _insert_test_receipt(connection, receipt_id="5" * 64, purpose="judge")
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
        with connection.transaction():
            connection.execute(
                "UPDATE aip_eval_execution_receipt SET claim_hash=%s WHERE receipt_id=%s",
                ("0" * 64, "3" * 64),
            )


def test_eval_runtime_can_read_only_its_tenant_and_cannot_insert(connection):
    _seed_isolated_authority(connection)
    connection.execute("SET ROLE aos_runtime")
    connection.execute("SELECT set_config('aos.org_id','org-org',true)")
    connection.execute("SELECT set_config('aos.project_id','dev-project',true)")
    assert connection.execute(
        "SELECT count(*) FROM aip_eval_executor_identity"
    ).fetchone()[0] == 1
    connection.execute("SELECT set_config('aos.org_id','dev-org',true)")
    assert connection.execute(
        "SELECT count(*) FROM aip_eval_executor_identity"
    ).fetchone()[0] == 0
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with connection.transaction():
            connection.execute("INSERT INTO aip_eval_issuer_root DEFAULT VALUES")


def test_eval_revocation_is_unique_and_append_only(connection):
    _seed_isolated_authority(connection)
    statement = """INSERT INTO aip_eval_authority_revocation
        (org_id,project_id,event_id,identity_id,revoked_at,owner_ref,
         approval_ref,reason_hash)
        VALUES ('org-org','dev-project',%s,'bg00y-test-target',now(),
                'bg00y-test-owner','{"testOnly":true}',%s)"""
    connection.execute(statement, ("event-1", "a" * 64))
    with pytest.raises(psycopg.errors.UniqueViolation):
        with connection.transaction():
            connection.execute(statement, ("event-2", "b" * 64))
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
        with connection.transaction():
            connection.execute(
                "DELETE FROM aip_eval_authority_revocation WHERE event_id='event-1'"
            )
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
        with connection.transaction():
            connection.execute("TRUNCATE aip_eval_authority_revocation")
