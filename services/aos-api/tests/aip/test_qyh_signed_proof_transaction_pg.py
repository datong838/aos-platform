"""Real signed fixture registration composed with caller state, not execution."""
from dataclasses import replace
from datetime import UTC, datetime
import os
import json
import secrets
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import pytest

from aos_api.aip_contracts import TenantContext
from aos_api.aip_eval_authority_store import AipEvalAuthorityStore
from aos_api.aip_eval_contracts import EvalRunEvent, EvalRunStatus
from aos_api.aip_eval_execution_authority import EvalExecutionRejected
from aos_api.aip_eval_report_proof_reader import PresentedEvalCaseProof, read_verified_skill_eval_report_from_persistence
from aos_api.aip_eval_runner import compute_eval_report_hash
import aos_api.aip_eval_writer_atomic as atomic
from aos_api.aip_signed_skill_eval_intent_store import SignedSkillEvalIntentStore
from aos_api.tenant_scope import TenantScope
from test_aip_eval_execution_authority import INPUT_HASH, _signed_pair
from test_aip_eval_persisted_authority_reader import _seed
from test_aip_eval_writer_atomic import _seed_source, _source_objects
from test_aip_eval_writer_transaction import _grant_isolated

SCOPE = TenantScope('org-org', 'dev-project')
TABLES = ['aip_eval_execution_receipt', 'aip_eval_report_revision', 'aip_eval_case_execution_proof']


def scope_role(conn, role, scope=SCOPE):
    conn.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(role)))
    conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", scope.key)


@pytest.fixture
def signed_source():
    original = os.environ['AOS_DATABASE_URL']
    parts = conninfo_to_dict(original)
    assert (parts['host'], parts['port']) == ('127.0.0.1', '18431')
    assert parts['dbname'].startswith('aos_test_') and parts['dbname'].endswith('_ti4_test')
    database = 'aos_test_' + uuid4().hex[:12] + '_ti4_test'
    with psycopg.connect(original, autocommit=True) as admin:
        assert admin.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0] == '7695416748450308141'
        admin.execute(sql.SQL('CREATE DATABASE {} TEMPLATE {}').format(sql.Identifier(database), sql.Identifier(parts['dbname'])))
        try:
            dsn = make_conninfo(**{**parts, 'dbname': database})
            suite, base = _source_objects()
            now = datetime.now(UTC)
            root, target, judge = _signed_pair(now, suite_ref=base.suite_ref)
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
                conn.execute("INSERT INTO twa_org(id,name) VALUES('org-org','test-only') ON CONFLICT DO NOTHING")
                conn.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','test-only') ON CONFLICT DO NOTHING")
                _seed_source(conn, suite)
                _seed(conn, root, target, judge, stage='identities', suite_ref=base.suite_ref)
                conn.execute('UPDATE aip_eval_run SET target_ref=%s,dataset_ref=%s,judge_ref=%s WHERE run_id=%s',
                    (Jsonb(base.target.model_dump(mode='json',by_alias=True)), Jsonb(base.dataset.model_dump(mode='json',by_alias=True)), Jsonb(base.judge.model_dump(mode='json',by_alias=True)),base.run_id))
                _grant_isolated(conn)
                scope_role(conn, 'aos_aip_eval_writer')
                intent = SignedSkillEvalIntentStore().create(conn, SCOPE, run_id=base.run_id, idempotency_key='new-test-intent', request_hash='a'*64)
                conn.execute('RESET ROLE')
                conn.execute("UPDATE aip_eval_run SET status='running',version=2,started_at=now() WHERE run_id=%s", (base.run_id,))
                for sequence, before, after in [(1,None,'queued'),(2,'queued','running')]:
                    conn.execute("""INSERT INTO aip_eval_run_event(org_id,project_id,event_id,run_id,sequence,event_type,from_status,to_status,payload_hash,actor,created_at)
                      VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,'test-only',now())""", (*SCOPE.key,'fixture-event-'+str(sequence),base.run_id,sequence,'run.'+after,before,after,'a'*64))
                scope_role(conn, 'aos_aip_eval_writer')
                dispatch = SignedSkillEvalIntentStore().claim(conn, SCOPE, intent_id=intent['intent_id'], expected_version=1, case_id='case-1', purpose='target', input_hash=INPUT_HASH)
                SignedSkillEvalIntentStore().observe(conn, SCOPE, dispatch_id=dispatch,state='result_observed',result_hash=target[1].output_hash)
                conn.commit()
            report = base.model_copy(update={'created_at': datetime.now(UTC)})
            report = report.model_copy(update={'content_hash': compute_eval_report_hash(report)})
            yield dsn, report, PresentedEvalCaseProof(target[0],target[1],judge[0],judge[1]), intent['intent_id']
        finally:
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(database)))


def view(dsn, intent_id):
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        scope_role(conn, 'aos_runtime')
        row = conn.execute("SELECT status,version FROM aip_eval_run WHERE run_id='run-1'").fetchone()
        counts = [conn.execute('SELECT count(*) AS n FROM '+table).fetchone()['n'] for table in TABLES]
        version = conn.execute('SELECT version FROM aip_skill_eval_intent WHERE intent_id=%s',(intent_id,)).fetchone()['version']
        events = conn.execute('SELECT count(*) AS n FROM aip_eval_run_event').fetchone()['n']
        return row, counts, version, events


def finish_fixture_run(conn, report):
    scope_role(conn, 'aos_runtime')
    event = EvalRunEvent(tenant=TenantContext(org_id=SCOPE.org_id,project_id=SCOPE.project_id),
        event_id='fixture-success',run_id=report.run_id,sequence=3,event_type='run.succeeded',
        from_status=EvalRunStatus.RUNNING,to_status=EvalRunStatus.SUCCEEDED,payload_hash='a'*64,
        actor='test-only',created_at=datetime.now(UTC))
    AipEvalAuthorityStore()._transition_eval_run_with_connection(conn,SCOPE,event,expected_version=2)
    scope_role(conn, 'aos_aip_eval_writer')


@pytest.mark.parametrize('scenario', ['commit','late_failure','bad_signature','wrong_tenant','wrong_role','read_committed'])
def test_signed_registration_shares_run_and_intent_transaction(signed_source, scenario):
    dsn, report, pair, intent = signed_source
    before = view(dsn, intent)
    assert before == ({'status':'running','version':2},[0,0,0],2,2)
    if scenario == 'bad_signature':
        pair = replace(pair, judge_receipt=pair.judge_receipt.model_copy(update={'signature_base64':'invalid'}))
    try:
        with psycopg.connect(dsn,row_factory=dict_row) as conn:
            conn.execute('SET TRANSACTION ISOLATION LEVEL '+('READ COMMITTED' if scenario=='read_committed' else 'SERIALIZABLE'))
            finish_fixture_run(conn, report)
            if scenario == 'wrong_tenant':
                scope_role(conn, 'aos_aip_eval_writer',TenantScope('dev-org','dev-project'))
            elif scenario == 'wrong_role':
                scope_role(conn,'aos_runtime')
            proof = atomic._persist_signed_skill_eval_report_with_connection(conn,report=report,
                expected_input_hashes={'case-1':INPUT_HASH},presented={'case-1':pair})
            assert proof.report_hash == report.content_hash
            conn.execute('UPDATE aip_skill_eval_intent SET version=version+1 WHERE intent_id=%s',(intent,))
            assert view(dsn,intent) == before, 'registration helper committed early'
            if scenario == 'late_failure':
                conn.execute('INSERT INTO aip_eval_case_execution_proof SELECT * FROM aip_eval_case_execution_proof')
            conn.commit()
    except EvalExecutionRejected:
        assert scenario in {'bad_signature','wrong_tenant','wrong_role','read_committed'}
        assert view(dsn,intent) == before
        return
    except psycopg.errors.UniqueViolation:
        assert scenario == 'late_failure'
        assert view(dsn,intent) == before
        return
    assert scenario == 'commit', 'negative scenario was accepted'
    assert view(dsn,intent) == ({'status':'succeeded','version':3},[2,1,1],3,3)
    with psycopg.connect(dsn,row_factory=dict_row) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        scope_role(conn,'aos_runtime')
        proof = read_verified_skill_eval_report_from_persistence(conn,report=report,evaluated_at=datetime.now(UTC))
        assert proof.report_hash == report.content_hash and len(proof.cases)==1


def test_default_writer_stays_off_without_identity(signed_source, monkeypatch):
    dsn, report, pair, intent = signed_source
    monkeypatch.delenv('AOS_AIP_EVAL_WRITER_CREDENTIAL_FILE',raising=False)
    before = view(dsn,intent)
    with pytest.raises(EvalExecutionRejected,match='independent Eval writer identity is unavailable'):
        atomic.persist_signed_skill_eval_report(expected_database='not-used',report=report,
            expected_input_hashes={'case-1':INPUT_HASH},presented={'case-1':pair})
    assert view(dsn,intent)==before


def test_connection_helper_rejects_autocommit_before_writes(signed_source):
    dsn, report, pair, intent = signed_source
    before = view(dsn,intent)
    with psycopg.connect(dsn,autocommit=True,row_factory=dict_row) as conn:
        with pytest.raises(EvalExecutionRejected,match='caller-owned Skill proof transaction'):
            atomic._persist_signed_skill_eval_report_with_connection(conn,report=report,
                expected_input_hashes={'case-1':INPUT_HASH},presented={'case-1':pair})
    assert view(dsn,intent)==before


def test_public_writer_keeps_real_independent_identity_checks(signed_source, tmp_path, monkeypatch):
    dsn, report, pair, intent = signed_source
    login = 'test_eval_writer_' + uuid4().hex[:16]
    password = secrets.token_urlsafe(32)
    with psycopg.connect(dsn,autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB NOREPLICATION PASSWORD {}').format(sql.Identifier(login),sql.Literal(password)))
        try:
            admin.execute(sql.SQL('GRANT aos_aip_eval_writer TO {}').format(sql.Identifier(login)))
            identity = tmp_path/'isolated-writer.json'
            identity.write_text(json.dumps({'schemaVersion':'aos.aip.eval-writer-identity/v1',
                'role':'aos_aip_eval_writer','dsn':make_conninfo(dsn,user=login,password=password)}))
            identity.chmod(0o600)
            monkeypatch.setenv('AOS_AIP_EVAL_WRITER_CREDENTIAL_FILE',str(identity))
            with psycopg.connect(dsn,row_factory=dict_row) as conn:
                conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
                finish_fixture_run(conn,report)
                conn.commit()
            proof = atomic.persist_signed_skill_eval_report(expected_database=conninfo_to_dict(dsn)['dbname'],
                report=report,expected_input_hashes={'case-1':INPUT_HASH},presented={'case-1':pair})
            assert proof.report_hash==report.content_hash
            assert view(dsn,intent)==({'status':'succeeded','version':3},[2,1,1],2,3)
        finally:
            monkeypatch.delenv('AOS_AIP_EVAL_WRITER_CREDENTIAL_FILE',raising=False)
            admin.execute(sql.SQL('REVOKE aos_aip_eval_writer FROM {}').format(sql.Identifier(login)))
            admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(login)))
