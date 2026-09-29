"""Test-only PostgreSQL role/RLS proof for an atomic Eval evidence insert."""
from __future__ import annotations

import hashlib
import os

import psycopg
import pytest
from psycopg.types.json import Jsonb

from aos_api.aip_eval_execution_authority import canonical_receipt_bytes
from test_aip_eval_execution_authority import NOW, TENANT, _signed_pair
from test_aip_eval_persisted_authority_reader import _seed
from test_aip_eval_report_proof_reader import _report

ROLE="aos_aip_eval_writer"
TABLES=("aip_eval_issuer_root","aip_eval_executor_identity",
        "aip_eval_authority_revocation","aip_eval_execution_receipt",
        "aip_eval_run","aip_eval_report_revision","aip_eval_case_execution_proof",
        "aip_eval_dataset_revision","aip_eval_suite_revision")


@pytest.fixture()
def connection():
    dsn=os.getenv("AOS_BG00AI_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("isolated BG-00ai PostgreSQL URL required")
    with psycopg.connect(dsn) as conn:
        assert conn.info.dbname=="aos_bg00ad_schema_v2_20260929"
        assert conn.info.port==5433
        assert conn.execute("SELECT count(*) FROM pg_roles WHERE rolname=%s",(ROLE,)).fetchone()[0]==1
        yield conn
        conn.rollback()


def _scope_as_writer(conn):
    conn.execute("SET LOCAL ROLE aos_aip_eval_writer")
    conn.execute("SELECT set_config('aos.org_id','org-org',true)")
    conn.execute("SELECT set_config('aos.project_id','dev-project',true)")


def _grant_isolated(conn):
    for table in TABLES:
        policy="bg00ai_test_writer_"+table
        conn.execute(f"""CREATE POLICY {policy} ON {table} TO aos_aip_eval_writer
          USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
             AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
             AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
        conn.execute(f"GRANT SELECT ON {table} TO aos_aip_eval_writer")
    for table in ("aip_eval_execution_receipt","aip_eval_report_revision",
                  "aip_eval_case_execution_proof"):
        conn.execute(f"GRANT INSERT ON {table} TO aos_aip_eval_writer")


def _receipt(conn, value):
    cert,receipt,_=value
    conn.execute("""INSERT INTO aip_eval_execution_receipt
      (org_id,project_id,receipt_id,run_id,case_id,purpose,identity_id,
       certificate_hash,suite_ref,executor_ref,claim_hash,input_hash,
       output_hash,actual_hash,expected_hash,passed,detail_code,
       occurred_at,signature_base64,created_at)
      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
      (TENANT.org_id,TENANT.project_id,receipt.receipt_id,receipt.run_id,
       receipt.case_id,receipt.purpose,cert.identity_id,receipt.certificate_hash,
       Jsonb(receipt.suite_ref.model_dump(mode='json',by_alias=True)),
       Jsonb(receipt.executor_ref.model_dump(mode='json',by_alias=True)),
       hashlib.sha256(canonical_receipt_bytes(receipt)).hexdigest(),
       receipt.input_hash,receipt.output_hash,receipt.actual_hash,
       receipt.expected_hash,receipt.passed,receipt.detail_code,
       receipt.occurred_at,receipt.signature_base64,NOW))


def _report_row(conn,report):
    conn.execute("""INSERT INTO aip_eval_report_revision
      (org_id,project_id,report_id,revision,content_hash,run_id,suite_ref,
       target_ref,dataset_ref,judge_ref,results,passed,failed,total,pass_rate,
       gate_passed,created_at)
      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
      (TENANT.org_id,TENANT.project_id,report.report_id,report.revision,
       report.content_hash,report.run_id,
       Jsonb(report.suite_ref.model_dump(mode='json',by_alias=True)),
       Jsonb(report.target.model_dump(mode='json',by_alias=True)),
       Jsonb(report.dataset.model_dump(mode='json',by_alias=True)),
       Jsonb(report.judge.model_dump(mode='json',by_alias=True)),
       Jsonb([r.model_dump(mode='json',by_alias=True) for r in report.results]),
       report.passed,report.failed,report.total,report.pass_rate,
       report.gate_passed,report.created_at))


def _proof(conn,report,target,judge,*,wrong_hash=False):
    target_hash=hashlib.sha256(canonical_receipt_bytes(target[1])).hexdigest()
    judge_hash=hashlib.sha256(canonical_receipt_bytes(judge[1])).hexdigest()
    conn.execute("""INSERT INTO aip_eval_case_execution_proof
      (org_id,project_id,run_id,case_id,report_id,report_revision,
       target_receipt_id,target_claim_hash,judge_receipt_id,judge_claim_hash,
       verified_at,created_at)
      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
      (TENANT.org_id,TENANT.project_id,report.run_id,"case-1",report.report_id,1,
       target[1].receipt_id,"f"*64 if wrong_hash else target_hash,
       judge[1].receipt_id,judge_hash,NOW,NOW))


def test_ungranted_writer_cannot_insert_receipt(connection):
    assert connection.execute("SELECT has_table_privilege(%s,'aip_eval_execution_receipt','INSERT')",(ROLE,)).fetchone()[0] is False
    _scope_as_writer(connection)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with connection.transaction():
            connection.execute('INSERT INTO aip_eval_execution_receipt DEFAULT VALUES')


def test_test_only_minimum_role_can_insert_atomic_proof_and_rollback(connection):
    root,target,judge=_signed_pair()
    _seed(connection,root,target,judge,stage='identities')
    report=_report()
    connection.execute("""UPDATE aip_eval_run SET status='succeeded',
      target_ref=%s,dataset_ref=%s,judge_ref=%s WHERE run_id='run-1'""",
      (Jsonb(report.target.model_dump(mode='json',by_alias=True)),
       Jsonb(report.dataset.model_dump(mode='json',by_alias=True)),
       Jsonb(report.judge.model_dump(mode='json',by_alias=True))))
    _grant_isolated(connection)
    assert connection.execute("SELECT has_table_privilege(%s,'aip_eval_issuer_root','INSERT')",(ROLE,)).fetchone()[0] is False
    assert connection.execute("SELECT has_table_privilege(%s,'aip_eval_run','UPDATE')",(ROLE,)).fetchone()[0] is False
    _scope_as_writer(connection)
    _receipt(connection,target)
    _receipt(connection,judge)
    _report_row(connection,report)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with connection.transaction():
            _proof(connection,report,target,judge,wrong_hash=True)
    _proof(connection,report,target,judge)
    for table in ("aip_eval_execution_receipt","aip_eval_report_revision",
                  "aip_eval_case_execution_proof"):
        expected=2 if table=="aip_eval_execution_receipt" else 1
        assert connection.execute('SELECT count(*) FROM '+table).fetchone()[0]==expected
    connection.execute("SELECT set_config('aos.org_id','dev-org',true)")
    assert connection.execute('SELECT count(*) FROM aip_eval_case_execution_proof').fetchone()[0]==0
    connection.rollback()
    for table in ("aip_eval_execution_receipt","aip_eval_report_revision",
                  "aip_eval_case_execution_proof"):
        assert connection.execute('SELECT count(*) FROM '+table).fetchone()[0]==0


def test_report_failure_rolls_back_both_receipts_and_proof_window(connection):
    root,target,judge=_signed_pair()
    _seed(connection,root,target,judge,stage='identities')
    report=_report()
    _grant_isolated(connection)
    _scope_as_writer(connection)
    _receipt(connection,target)
    _receipt(connection,judge)
    _report_row(connection,report)
    with pytest.raises(psycopg.errors.UniqueViolation):
        _report_row(connection,report)
    connection.rollback()
    for table in ("aip_eval_execution_receipt","aip_eval_report_revision",
                  "aip_eval_case_execution_proof"):
        assert connection.execute('SELECT count(*) FROM '+table).fetchone()[0]==0
