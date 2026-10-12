"""Native journal plus real signed fixtures; no Target/Judge execution or resend."""
import base64
from datetime import UTC, datetime
import os
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import pytest

from aos_api.aip_eval_execution_authority import canonical_receipt_bytes
from aos_api.aip_eval_report_proof_reader import PresentedEvalCaseProof
from aos_api.aip_eval_runner import compute_eval_report_hash
from aos_api.aip_eval_writer_atomic import _persist_signed_skill_eval_report_with_connection
import aos_api.aip_eval_writer_reconcile as reconcile
from aos_api.aip_signed_skill_eval_intent_store import SignedSkillEvalIntentStore
from test_aip_eval_execution_authority import INPUT_HASH, _signed_pair
from test_aip_eval_persisted_authority_reader import _seed
from test_aip_eval_writer_atomic import _seed_source, _source_objects
from test_aip_eval_writer_transaction import _grant_isolated
from test_qyh_signed_proof_transaction_pg import finish_fixture_run, scope_role, SCOPE


def connection(dsn, *, readonly=False):
    conn = psycopg.connect(dsn,row_factory=dict_row)
    conn.execute('SET TRANSACTION ISOLATION LEVEL '+('REPEATABLE READ READ ONLY' if readonly else 'SERIALIZABLE'))
    scope_role(conn,'aos_runtime' if readonly else 'aos_aip_eval_writer')
    return conn


def resign(receipt, key, at):
    changed = receipt.model_copy(update={'occurred_at':at})
    return changed.model_copy(update={'signature_base64':base64.b64encode(key.sign(canonical_receipt_bytes(changed))).decode()})


def database_clock(dsn):
    with psycopg.connect(dsn) as conn:
        conn.read_only=True
        return conn.execute('SELECT clock_timestamp()').fetchone()[0]


@pytest.fixture
def journal(request):
    variant = getattr(request,'param','valid')
    original = os.environ['AOS_DATABASE_URL']; parts = conninfo_to_dict(original)
    assert (parts['host'],parts['port'])==('127.0.0.1','18431')
    assert parts['dbname'].startswith('aos_test_') and parts['dbname'].endswith('_ti4_test')
    database = 'aos_test_'+uuid4().hex[:12]+'_ti4_test'
    store = SignedSkillEvalIntentStore()
    with psycopg.connect(original,autocommit=True) as admin:
        assert admin.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]=='7695416748450308141'
        admin.execute(sql.SQL('CREATE DATABASE {} TEMPLATE {}').format(sql.Identifier(database),sql.Identifier(parts['dbname'])))
        try:
            dsn = make_conninfo(**{**parts,'dbname':database})
            suite, base = _source_objects()
            root, target, judge = _signed_pair(datetime.now(UTC),suite_ref=base.suite_ref)
            with psycopg.connect(dsn,row_factory=dict_row) as conn:
                conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
                conn.execute("INSERT INTO twa_org(id,name) VALUES('org-org','test-only') ON CONFLICT DO NOTHING")
                conn.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','test-only') ON CONFLICT DO NOTHING")
                _seed_source(conn,suite)
                _seed(conn,root,target,judge,stage='identities',suite_ref=base.suite_ref)
                conn.execute('UPDATE aip_eval_run SET dataset_ref=%s WHERE run_id=%s',
                    (Jsonb(base.dataset.model_dump(mode='json',by_alias=True)),base.run_id))
                _grant_isolated(conn)
                scope_role(conn,'aos_aip_eval_writer')
                intent = store.create(conn,SCOPE,run_id=base.run_id,idempotency_key='test-journal-once',request_hash='a'*64)
                conn.execute('RESET ROLE')
                conn.execute("UPDATE aip_eval_run SET status='running',version=2,started_at=now() WHERE run_id=%s",(base.run_id,))
                for sequence,before,after in [(1,None,'queued'),(2,'queued','running')]:
                    conn.execute("""INSERT INTO aip_eval_run_event(org_id,project_id,event_id,run_id,sequence,event_type,from_status,to_status,payload_hash,actor,created_at)
                      VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,'test-only',now())""",(*SCOPE.key,'journal-event-'+str(sequence),base.run_id,sequence,'run.'+after,before,after,'a'*64))
                conn.commit()
            with connection(dsn) as conn:
                target_dispatch = store.claim(conn,SCOPE,intent_id=intent['intent_id'],expected_version=1,
                    case_id='case-1',purpose='target',input_hash='f'*64 if variant=='wrong_input' else INPUT_HASH)
                if variant=='judge_before_target':
                    judge_dispatch = store.claim(conn,SCOPE,intent_id=intent['intent_id'],expected_version=2,
                        case_id='case-1',purpose='judge',input_hash=INPUT_HASH)
                conn.commit()
            target_receipt = resign(target[1],target[2],target[1].occurred_at if variant=='backdated_target' else database_clock(dsn))
            with connection(dsn) as conn:
                store.observe(conn,SCOPE,dispatch_id=target_dispatch,state='result_observed',result_hash=target_receipt.output_hash)
                if variant not in {'missing_judge','judge_before_target'}:
                    judge_dispatch = store.claim(conn,SCOPE,intent_id=intent['intent_id'],expected_version=2,
                        case_id='case-1',purpose='judge',input_hash=INPUT_HASH)
                conn.commit()
            judge_receipt = resign(judge[1],judge[2],database_clock(dsn))
            if variant!='missing_judge':
                with connection(dsn) as conn:
                    store.observe(conn,SCOPE,dispatch_id=judge_dispatch,
                        state='unknown' if variant=='unknown_judge' else 'result_observed',
                        result_hash=None if variant=='unknown_judge' else judge_receipt.output_hash)
                    conn.commit()
            pair = PresentedEvalCaseProof(target[0],target_receipt,judge[0],judge_receipt)
            report = base.model_copy(update={'created_at':database_clock(dsn)})
            report = report.model_copy(update={'content_hash':compute_eval_report_hash(report)})
            with psycopg.connect(dsn,row_factory=dict_row) as conn:
                conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
                finish_fixture_run(conn,report)
                at = conn.execute('SELECT transaction_timestamp() AS at').fetchone()['at']
                assert compute_eval_report_hash(report)==report.content_hash
                assert report.created_at<=at, (report.created_at.isoformat(),at.isoformat())
                _persist_signed_skill_eval_report_with_connection(conn,report=report,
                    expected_input_hashes={'case-1':INPUT_HASH},presented={'case-1':pair})
                version = conn.execute('UPDATE aip_skill_eval_intent SET version=version+1 WHERE intent_id=%s RETURNING version',(intent['intent_id'],)).fetchone()['version']
                conn.commit()
            yield dsn, report, pair, intent['intent_id'], version, variant
        finally:
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(database)))


def kwargs(journal):
    _,report,pair,intent,version,_ = journal
    return dict(report=report,expected_input_hashes={'case-1':INPUT_HASH},presented={'case-1':pair},
                intent_id=intent,expected_request_hash='a'*64,expected_intent_version=version,expected_run_version=3)


def counts(conn):
    return [conn.execute('SELECT count(*) AS n FROM '+table).fetchone()['n'] for table in
        ['aip_eval_run_event','aip_eval_execution_receipt','aip_eval_report_revision','aip_eval_case_execution_proof',
         'aip_skill_eval_intent','aip_skill_eval_dispatch','aip_skill_eval_dispatch_observation']]


@pytest.mark.parametrize('journal',['valid','missing_judge','unknown_judge','wrong_input','backdated_target','judge_before_target'],indirect=True)
def test_report_proof_alone_does_not_complete_dispatch_journal(journal):
    dsn,report,pair,_,_,variant=journal
    with connection(dsn,readonly=True) as conn:
        before=counts(conn)
        old = reconcile.reconcile_signed_skill_eval_report(conn,report=report,
            expected_input_hashes={'case-1':INPUT_HASH},presented={'case-1':pair})
        assert old.state=='COMPLETE', 'original complete Report proof is prerequisite'
        result=reconcile.reconcile_signed_skill_eval_intent(conn,**kwargs(journal))
        assert result.state==('COMPLETE' if variant=='valid' else 'UNKNOWN')
        assert (result.proof is not None)==(variant=='valid')
        assert counts(conn)==before


@pytest.mark.parametrize('field,value',[('expected_request_hash','f'*64),('expected_intent_version',999),('expected_run_version',999),('intent_id','missing')])
def test_exact_intent_binding_mismatch_is_unknown(journal,field,value):
    data=kwargs(journal); data[field]=value
    with connection(journal[0],readonly=True) as conn:
        before=counts(conn)
        assert reconcile.reconcile_signed_skill_eval_intent(conn,**data).state=='UNKNOWN'
        assert counts(conn)==before


@pytest.mark.parametrize('mode',['read_write','canary'])
def test_wrong_snapshot_or_tenant_never_accepts(journal,mode):
    with connection(journal[0],readonly=mode!='read_write') as conn:
        if mode=='canary':
            conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
        assert reconcile.reconcile_signed_skill_eval_intent(conn,**kwargs(journal)).state=='UNKNOWN'
