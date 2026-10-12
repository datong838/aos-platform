"""Complete atomic ending with isolated signed fixtures, never real execution."""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import UTC, datetime, timedelta
import os
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from aos_api.aip_contracts import TenantContext
from aos_api.aip_eval_contracts import EvalRunEvent, EvalRunStatus
from aos_api.aip_eval_execution_authority import EvalExecutionRejected
from aos_api.aip_eval_report_proof_reader import PresentedEvalCaseProof, read_verified_skill_eval_report_from_persistence
from aos_api.aip_eval_runner import compute_eval_report_hash
from aos_api.aip_eval_writer_reconcile import reconcile_signed_skill_eval_intent
from aos_api.aip_signed_skill_eval_intent_store import SignedSkillEvalIntentStore
from aos_api.aip_skill_eval_atomic_finisher import finish_signed_skill_eval_with_connection
from test_aip_eval_execution_authority import INPUT_HASH, _signed_pair
from test_aip_eval_persisted_authority_reader import _seed
from test_aip_eval_writer_atomic import _seed_source, _source_objects
from test_aip_eval_writer_transaction import _grant_isolated
from test_qyh_signed_proof_transaction_pg import SCOPE, scope_role, view
from test_qyh_signed_intent_reconciliation_pg import database_clock, resign


@pytest.fixture
def complete_source():
    original = os.environ['AOS_DATABASE_URL']; parts = conninfo_to_dict(original)
    assert parts['host'] == '127.0.0.1' and parts['port'] == '18431'
    assert parts['dbname'].startswith('aos_test_') and parts['dbname'].endswith('_ti4_test')
    database = 'aos_test_' + uuid4().hex[:12] + '_ti4_test'
    login = 'skill_finisher_test_' + uuid4().hex[:12]
    with psycopg.connect(original, autocommit=True) as admin:
        assert admin.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0] == '7695416748450308141'
        new_role = admin.execute("SELECT 1 FROM pg_roles WHERE rolname='aos_skill_eval_finisher'").fetchone() is None
        if new_role: admin.execute('CREATE ROLE aos_skill_eval_finisher NOLOGIN NOINHERIT')
        admin.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT').format(sql.Identifier(login)))
        admin.execute(sql.SQL('GRANT aos_aip_eval_writer,aos_skill_eval_finisher TO {}').format(sql.Identifier(login)))
        admin.execute(sql.SQL('CREATE DATABASE {} TEMPLATE {}').format(sql.Identifier(database), sql.Identifier(parts['dbname'])))
        dsn = make_conninfo(**{**parts, 'dbname': database})
        try:
            suite, base = _source_objects(); store = SignedSkillEvalIntentStore()
            root, target, judge = _signed_pair(database_clock(dsn), suite_ref=base.suite_ref)
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                conn.execute("INSERT INTO twa_org(id,name) VALUES('org-org','test-only') ON CONFLICT DO NOTHING")
                conn.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','test-only') ON CONFLICT DO NOTHING")
                _seed_source(conn, suite)
                _seed(conn, root, target, judge, stage='identities', suite_ref=base.suite_ref)
                conn.execute('UPDATE aip_eval_run SET target_ref=%s,dataset_ref=%s,judge_ref=%s WHERE run_id=%s',
                    (Jsonb(base.target.model_dump(mode='json',by_alias=True)), Jsonb(base.dataset.model_dump(mode='json',by_alias=True)), Jsonb(base.judge.model_dump(mode='json',by_alias=True)),base.run_id))
                _grant_isolated(conn)
                for table in ['aip_eval_run', 'aip_eval_run_event']:
                    conn.execute('CREATE POLICY finisher_fixture ON '+table+" TO aos_skill_eval_finisher USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true)) WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))")
                conn.execute('GRANT SELECT,UPDATE(status,version,started_at,finished_at) ON aip_eval_run TO aos_skill_eval_finisher')
                conn.execute('GRANT SELECT,INSERT ON aip_eval_run_event TO aos_skill_eval_finisher')
                conn.commit()
                conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE'); scope_role(conn,'aos_aip_eval_writer')
                intent = store.create(conn,SCOPE,run_id=base.run_id,idempotency_key='new-finisher-fixture',request_hash='a'*64)
                conn.execute('RESET ROLE')
                conn.execute("UPDATE aip_eval_run SET status='running',version=2,started_at=now() WHERE run_id=%s",(base.run_id,))
                for seq,before,after in [(1,None,'queued'),(2,'queued','running')]:
                    conn.execute("INSERT INTO aip_eval_run_event(org_id,project_id,event_id,run_id,sequence,event_type,from_status,to_status,payload_hash,actor,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,'test-only',now())",(*SCOPE.key,'initial-'+str(seq),base.run_id,seq,'run.'+after,before,after,'a'*64))
                conn.commit()
            receipts=[]
            for purpose,pair,version in [('target',target,1),('judge',judge,2)]:
                with psycopg.connect(dsn,row_factory=dict_row) as conn:
                    conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE');scope_role(conn,'aos_aip_eval_writer')
                    dispatch=store.claim(conn,SCOPE,intent_id=intent['intent_id'],expected_version=version,case_id='case-1',purpose=purpose,input_hash=INPUT_HASH)
                    conn.commit()
                receipt=resign(pair[1],pair[2],database_clock(dsn));receipts.append(receipt)
                with psycopg.connect(dsn,row_factory=dict_row) as conn:
                    conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE');scope_role(conn,'aos_aip_eval_writer')
                    store.observe(conn,SCOPE,dispatch_id=dispatch,state='result_observed',result_hash=receipt.output_hash);conn.commit()
            report=base.model_copy(update={'created_at':database_clock(dsn)})
            report=report.model_copy(update={'content_hash':compute_eval_report_hash(report)})
            pair=PresentedEvalCaseProof(target[0],receipts[0],judge[0],receipts[1])
            event=EvalRunEvent(tenant=TenantContext(org_id=SCOPE.org_id,project_id=SCOPE.project_id),event_id='new-finish',run_id=report.run_id,sequence=3,event_type='run.succeeded',from_status=EvalRunStatus.RUNNING,to_status=EvalRunStatus.SUCCEEDED,payload_hash=report.content_hash,actor='test-only',created_at=report.created_at)
            yield dsn, make_conninfo(**{**parts,'dbname':database,'user':login}), report,pair,intent['intent_id'],event
        finally:
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(database)))
            admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(login)))
            if new_role:admin.execute('DROP ROLE aos_skill_eval_finisher')


@pytest.mark.parametrize('scenario',['commit','signature','input','intent-version','run-version','request','wrong-tenant','wide-acl','read-committed','autocommit','late-failure','caught-failure','future-event','wrong-event-type','boolean-version'])
def test_complete_ending_is_atomic_and_scoped(complete_source, scenario):
    admin_dsn,dsn,report,pair,intent,event=complete_source
    before=view(admin_dsn,intent);assert before==({'status':'running','version':2},[0,0,0],3,2)
    if scenario in {'late-failure','caught-failure'}:
        with psycopg.connect(admin_dsn) as admin:
            admin.execute(sql.SQL('ALTER TABLE aip_eval_case_execution_proof ADD CONSTRAINT force_late_failure CHECK(report_id <> {})').format(sql.Literal(report.report_id)))
    if scenario=='wide-acl':
        with psycopg.connect(admin_dsn) as admin:admin.execute('GRANT UPDATE ON aip_eval_run TO aos_skill_eval_finisher')
    if scenario=='signature':pair=replace(pair,judge_receipt=pair.judge_receipt.model_copy(update={'signature_base64':'invalid'}))
    if scenario=='future-event':event=event.model_copy(update={'created_at':event.created_at+timedelta(days=1)})
    if scenario=='wrong-event-type':event=event.model_copy(update={'event_type':'run.failed'})
    with psycopg.connect(dsn,row_factory=dict_row,autocommit=scenario=='autocommit') as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL '+('READ COMMITTED' if scenario=='read-committed' else 'SERIALIZABLE'))
        conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",('dev-org' if scenario=='wrong-tenant' else SCOPE.org_id,SCOPE.project_id))
        arguments=dict(expected_database=conn.info.dbname,scope=SCOPE,intent_id=intent,expected_intent_version=4 if scenario=='intent-version' else 3,request_hash='b'*64 if scenario=='request' else 'a'*64,event=event,expected_run_version=3 if scenario=='run-version' else 2,report=report,expected_input_hashes={'case-1':'f'*64 if scenario=='input' else INPUT_HASH},presented={'case-1':pair})
        if scenario=='boolean-version':arguments['expected_run_version']=True
        if scenario=='commit':
            proof=finish_signed_skill_eval_with_connection(conn,**arguments);assert proof.report_hash==report.content_hash
            assert view(admin_dsn,intent)==before,'internal helper committed'
            conn.commit()
        else:
            expected_error = psycopg.errors.CheckViolation if scenario in {'late-failure','caught-failure'} else (EvalExecutionRejected,RuntimeError)
            reasons={'signature':'signature','input':'observation','intent-version':'intent version',
                'run-version':'eval run version','request':'intent version','wrong-tenant':'tenant',
                'wide-acl':'capabilities','read-committed':'transaction','autocommit':'caller-owned',
                'late-failure':'force_late_failure','caught-failure':'force_late_failure',
                'future-event':'event','wrong-event-type':'event','boolean-version':'event'}
            with pytest.raises(expected_error,match=reasons[scenario]):
                finish_signed_skill_eval_with_connection(conn,**arguments)
            if scenario=='caught-failure':conn.commit()
            else:conn.rollback()
    if scenario!='commit':assert view(admin_dsn,intent)==before
    else:
        assert view(admin_dsn,intent)==({'status':'succeeded','version':3},[2,1,1],4,3)
        with psycopg.connect(admin_dsn,row_factory=dict_row) as reader:
            reader.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            scope_role(reader,'aos_runtime')
            proof=read_verified_skill_eval_report_from_persistence(reader,report=report,evaluated_at=database_clock(admin_dsn))
            assert proof.report_hash==report.content_hash
            outcome=reconcile_signed_skill_eval_intent(reader,report=report,
                expected_input_hashes={'case-1':INPUT_HASH},presented={'case-1':pair},
                intent_id=intent,expected_request_hash='a'*64,
                expected_intent_version=4,expected_run_version=3)
            assert outcome.state=='COMPLETE'


def test_two_native_finishers_have_one_commit_without_retry(complete_source):
    admin_dsn,dsn,report,pair,intent,event=complete_source
    barrier=Barrier(2)
    def finish_once():
        with psycopg.connect(dsn,row_factory=dict_row) as conn:
            conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
            conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",SCOPE.key)
            conn.execute("SET LOCAL lock_timeout='5s'")
            barrier.wait(timeout=5)
            try:
                finish_signed_skill_eval_with_connection(conn,expected_database=conn.info.dbname,
                    scope=SCOPE,intent_id=intent,expected_intent_version=3,request_hash='a'*64,
                    event=event,expected_run_version=2,report=report,
                    expected_input_hashes={'case-1':INPUT_HASH},presented={'case-1':pair})
                conn.commit()
                return 'committed'
            except (psycopg.errors.SerializationFailure,EvalExecutionRejected):
                conn.rollback()
                return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:finish_once(),range(2)))
    assert sorted(results)==['committed','conflict']
    assert view(admin_dsn,intent)==({'status':'succeeded','version':3},[2,1,1],4,3)
