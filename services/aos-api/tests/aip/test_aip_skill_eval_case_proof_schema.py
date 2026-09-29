"""Test-only a0v114 Skill Eval proof sidecar; no current database writes."""
from __future__ import annotations

import os

import psycopg
import pytest
from psycopg.types.json import Jsonb

from aos_api.aip_eval_execution_authority import canonical_receipt_bytes
from test_aip_eval_execution_authority import NOW, SUITE, TARGET, JUDGE, TENANT, _signed_pair
from test_aip_eval_persisted_authority_reader import _seed
import hashlib


@pytest.fixture()
def connection():
    dsn = os.getenv("AOS_BG00AD_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("isolated BG-00ad PostgreSQL URL required")
    with psycopg.connect(dsn) as conn:
        assert conn.info.dbname == "aos_bg00ad_schema_v2_20260929"
        assert conn.info.port == 5433
        yield conn
        conn.rollback()


def test_skill_eval_case_proof_schema_is_tenant_scoped_and_append_only(connection):
    assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "a0v_114"
    row = connection.execute("""SELECT relrowsecurity,relforcerowsecurity,
        has_table_privilege('aos_runtime',oid,'SELECT'),
        has_table_privilege('aos_runtime',oid,'INSERT'),
        has_table_privilege('aos_runtime',oid,'UPDATE'),
        has_table_privilege('aos_runtime',oid,'DELETE')
        FROM pg_class WHERE oid='aip_eval_case_execution_proof'::regclass""").fetchone()
    assert row == (True,True,True,True,False,False)
    assert connection.execute("SELECT count(*) FROM aip_eval_case_execution_proof").fetchone()[0] == 0
    policy = connection.execute("""SELECT roles,qual,with_check FROM pg_policies
        WHERE schemaname='public' AND tablename='aip_eval_case_execution_proof'""").fetchone()
    assert policy[0] == ['aos_runtime']
    assert 'aos.org_id' in policy[1] and 'aos.project_id' in policy[2]
    triggers = connection.execute("""SELECT tgname FROM pg_trigger
        WHERE tgrelid='aip_eval_case_execution_proof'::regclass AND NOT tgisinternal""").fetchall()
    assert len(triggers) == 2


def _insert_proof(conn, target, judge, **changes):
    values = dict(
        org_id=TENANT.org_id, project_id=TENANT.project_id,
        run_id="run-1", case_id="case-1", report_id="bg00ad-report",
        report_revision=1, target_purpose="target",
        target_receipt_id=target[1].receipt_id,
        target_claim_hash=hashlib.sha256(canonical_receipt_bytes(target[1])).hexdigest(),
        judge_purpose="judge", judge_receipt_id=judge[1].receipt_id,
        judge_claim_hash=hashlib.sha256(canonical_receipt_bytes(judge[1])).hexdigest(),
        verified_at=NOW, created_at=NOW,
    )
    values.update(changes)
    conn.execute("""INSERT INTO aip_eval_case_execution_proof
      (org_id,project_id,run_id,case_id,report_id,report_revision,
       target_purpose,target_receipt_id,target_claim_hash,judge_purpose,
       judge_receipt_id,judge_claim_hash,verified_at,created_at)
      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
      tuple(values.values()))


def test_skill_proof_exact_fks_replay_and_append_only(connection):
    root,target,judge = _signed_pair()
    _seed(connection,root,target,judge)
    connection.execute("""INSERT INTO aip_eval_report_revision
      (org_id,project_id,report_id,revision,content_hash,run_id,
       suite_ref,target_ref,dataset_ref,judge_ref,results,passed,failed,total,
       pass_rate,gate_passed,created_at)
      VALUES (%s,%s,'bg00ad-report',1,%s,'run-1',%s,%s,%s,%s,%s,1,0,1,1.0,true,%s)""",
      (TENANT.org_id,TENANT.project_id,'a'*64,
       Jsonb(SUITE.model_dump(mode='json',by_alias=True)),
       Jsonb(TARGET.model_dump(mode='json',by_alias=True)),
       Jsonb({'testOnly':True}),Jsonb(JUDGE.model_dump(mode='json',by_alias=True)),
       Jsonb([{'caseId':'case-1','testOnly':True}]),NOW))
    for change, error in (
        ({'run_id':'other-run'}, psycopg.errors.ForeignKeyViolation),
        ({'case_id':'other-case'}, psycopg.errors.ForeignKeyViolation),
        ({'target_purpose':'judge'}, psycopg.errors.CheckViolation),
        ({'target_claim_hash':'f'*64}, psycopg.errors.ForeignKeyViolation),
    ):
        with pytest.raises(error):
            with connection.transaction():
                _insert_proof(connection,target,judge,**change)
    _insert_proof(connection,target,judge)
    with pytest.raises(psycopg.errors.UniqueViolation):
        with connection.transaction():
            _insert_proof(connection,target,judge)
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
        with connection.transaction():
            connection.execute("""UPDATE aip_eval_case_execution_proof
                SET target_claim_hash=%s WHERE run_id='run-1'""", ('b'*64,))
    connection.execute('SET LOCAL ROLE aos_runtime')
    connection.execute("SELECT set_config('aos.org_id','org-org',true)")
    connection.execute("SELECT set_config('aos.project_id','dev-project',true)")
    assert connection.execute('SELECT count(*) FROM aip_eval_case_execution_proof').fetchone()[0] == 1
    connection.execute("SELECT set_config('aos.org_id','dev-org',true)")
    assert connection.execute('SELECT count(*) FROM aip_eval_case_execution_proof').fetchone()[0] == 0
