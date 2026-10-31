"""Unit tests of producer transaction composition, not real PG or authority."""
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row
from aos_api.aip_contracts import TenantContext
from aos_api.aip_eval_contracts import EvalReportRevision, EvalRunEvent
from aos_api.aip_eval_runner import compute_eval_report_hash
from aos_api.tenant_scope import TenantScope
import aos_api.aip_skill_eval_producer_transactions as module

SCOPE=TenantScope('org-org','dev-project')


class FakeConnection:
    autocommit=False
    row_factory=staticmethod(dict_row)
    info=SimpleNamespace(transaction_status=TransactionStatus.IDLE)

    def __init__(self):
        self.events=[];self.fail_commit=False;self.fail_close=False;self.readonly=False
        self.dispatch=dict(dispatch_id='dispatch-1',case_id='case-1',purpose='target',input_hash='b'*64)
        self.role='producer-login';self.database='fixture_database'

    @contextmanager
    def transaction(self):
        self.events.append('begin')
        try:yield
        except Exception:
            self.events.append('rollback');raise
        self.events.append('commit')
        if self.fail_commit:raise RuntimeError('private commit transport text')

    def execute(self,sql,parameters=()):
        self.events.append(sql)
        if sql=='SET LOCAL ROLE aos_aip_eval_writer':self.role='aos_aip_eval_writer'
        if 'current_user AS role' in sql:
            return SimpleNamespace(fetchone=lambda:dict(role=self.role,database_name=self.database,org_id=SCOPE.org_id,project_id=SCOPE.project_id,
                isolation='repeatable read' if self.readonly else 'serializable',readonly='on' if self.readonly else 'off'))
        return SimpleNamespace(fetchone=lambda:self.dispatch)


class ProducerTransactionTests(unittest.TestCase):
    def setUp(self):
        self.conn=FakeConnection();self.store=Mock()
        self.store.get.return_value=dict(run_id='run-1',request_hash='a'*64,version=2)
        self.store.create.return_value=dict(intent_id='intent-1',run_id='run-1',request_hash='a'*64,version=1)
        self.store.claim.return_value='dispatch-1';self.store.observations.return_value=[]
        @contextmanager
        def writer(**_kwargs):
            self.conn.role='producer-login';self.conn.readonly=False
            yield self.conn
            self.conn.events.append('close')
            if self.conn.fail_close:raise RuntimeError('private close detail')
        @contextmanager
        def reader(*args,**kwargs):
            self.conn.role='aos_runtime';self.conn.readonly=True
            yield self.conn
        self.writer=Mock(side_effect=writer);self.reader=Mock(side_effect=reader)
        for name,value in [('configured_skill_producer_connection',Mock(return_value=self.writer)),
                           ('connect_read_only',self.reader),('require_skill_producer_identity',Mock()),
                           ('SignedSkillEvalIntentStore',Mock(return_value=self.store))]:
            p=patch.object(module,name,value);p.start();self.addCleanup(p.stop)
        self.owner=module.SkillEvalProducerTransactions(expected_database='fixture_database')
        self.request=module.SkillDispatchRequest(intent_id='intent-1',run_id='run-1',request_hash='a'*64,
            expected_intent_version=1,case_id='case-1',purpose='target',input_hash='b'*64)

    def test_claim_returns_only_after_commit_and_close(self):
        result=self.owner.claim_dispatch(SCOPE,self.request)
        self.assertEqual(result.dispatch_id,'dispatch-1');self.assertTrue(result.claim_committed)
        self.assertEqual(self.conn.events[-2:],['commit','close'])
        self.store.claim.assert_called_once_with(self.conn,SCOPE,intent_id='intent-1',expected_version=1,
            case_id='case-1',purpose='target',input_hash='b'*64)
        self.assertIn('SET LOCAL ROLE aos_aip_eval_writer',self.conn.events)

    def test_commit_and_close_uncertainty_never_return_ticket_or_retry(self):
        for kind in ['fail_commit','fail_close']:
            setattr(self.conn,kind,True)
            with self.assertRaises(module.SkillProducerOutcomeUnknown) as caught:self.owner.claim_dispatch(SCOPE,self.request)
            self.assertNotIn('private',str(caught.exception))
            setattr(self.conn,kind,False)
        self.assertEqual(self.store.claim.call_count,2)

    def test_existing_dispatch_is_recorded_not_new_claim_permission(self):
        self.store.claim.return_value=None
        result=self.owner.claim_dispatch(SCOPE,self.request)
        self.assertFalse(result.claim_committed);self.assertEqual(result.dispatch_id,'dispatch-1')

    def test_binding_drift_rejected_before_claim(self):
        self.store.get.return_value=dict(run_id='other',request_hash='a'*64,version=1)
        with self.assertRaises(ValueError):self.owner.claim_dispatch(SCOPE,self.request)
        self.store.claim.assert_not_called();self.assertIn('rollback',self.conn.events)

    def test_observation_binds_dispatch_to_original_request(self):
        self.owner.observe_dispatch(SCOPE,self.request,dispatch_id='dispatch-1',state='unknown',result_hash=None)
        self.store.observe.assert_called_once_with(self.conn,SCOPE,dispatch_id='dispatch-1',state='unknown',result_hash=None)
        self.conn.dispatch['input_hash']='c'*64
        with self.assertRaises(ValueError):self.owner.observe_dispatch(SCOPE,self.request,dispatch_id='dispatch-1',state='result_observed',result_hash='d'*64)
        self.assertEqual(self.store.observe.call_count,1)

    def test_reconcile_missing_is_unknown_and_never_opens_writer(self):
        self.conn.dispatch=None
        result=self.owner.reconcile_dispatch(SCOPE,self.request)
        self.assertEqual(result.state,'UNKNOWN');self.writer.assert_not_called();self.store.claim.assert_not_called()
        self.reader.assert_called_once_with(scope=SCOPE,inherit_scope=False)

    def test_reconcile_existing_returns_original_observations_without_writes(self):
        self.store.observations.return_value=[dict(state='unknown',result_hash=None,observed_at=None)]
        result=self.owner.reconcile_dispatch(SCOPE,self.request)
        self.assertEqual(result.state,'RECORDED');self.assertFalse(result.claim_committed)
        self.assertEqual(result.observations[0]['state'],'unknown');self.store.observe.assert_not_called()
        self.writer.assert_not_called()

    def test_invalid_request_or_observation_rejected_before_connection(self):
        for override in [dict(expected_intent_version=True),dict(purpose='other'),dict(input_hash='sha256:'+'b'*64)]:
            fields=dict(vars(self.request));fields.update(override)
            with self.assertRaises(ValueError):module.SkillDispatchRequest(**fields)
        with self.assertRaises(ValueError):self.owner.observe_dispatch(SCOPE,self.request,dispatch_id='dispatch-1',state='unknown',result_hash='d'*64)
        self.writer.assert_not_called()

    def test_disabled_writer_has_no_fallback(self):
        with patch.object(module,'configured_skill_producer_connection',return_value=None),self.assertRaises(RuntimeError):
            self.owner.claim_dispatch(SCOPE,self.request)
        self.writer.assert_not_called()

    def test_create_intent_uses_original_store_and_confirms_commit(self):
        result=self.owner.create_intent(SCOPE,run_id='run-1',idempotency_key='key-1',request_hash='a'*64)
        self.assertEqual(result['intent_id'],'intent-1');self.assertEqual(self.conn.events[-2:],['commit','close'])
        self.store.create.assert_called_once_with(self.conn,SCOPE,run_id='run-1',idempotency_key='key-1',request_hash='a'*64)

    def report_and_event(self):
        tenant=TenantContext(org_id=SCOPE.org_id,project_id=SCOPE.project_id)
        def ref(kind,name):return dict(assetType=kind,assetId=name,revision='1',contentHash='a'*64)
        report=EvalReportRevision(tenant=tenant,reportId='report-1',revision=1,contentHash='a'*64,runId='run-1',
            suiteRef=ref('eval_suite','suite-1'),target=ref('skill_template','skill-1'),
            dataset=dict(datasetId='data-1',revision=1,contentHash='a'*64,sourceHash='a'*64,redactionPolicy=ref('policy','redaction-1')),
            judge=dict(judgeId='judge-1',revision=1,contentHash='a'*64),
            results=[dict(caseId='case-1',passed=True,actualHash='a'*64,expectedHash=None,detailCode='PASS',durationMs=1)],
            passed=1,failed=0,total=1,passRate=1.0,gatePassed=True,createdAt=datetime.now(timezone.utc))
        report=report.model_copy(update={'content_hash':compute_eval_report_hash(report)})
        event=EvalRunEvent(tenant=tenant,eventId='event-1',runId='run-1',sequence=3,eventType='run.succeeded',
            fromStatus='running',toStatus='succeeded',payloadHash=report.content_hash,actor='test-only',createdAt=report.created_at)
        return report,event

    def finish_arguments(self):
        report,event=self.report_and_event()
        return dict(intent_id='intent-1',expected_intent_version=3,request_hash='a'*64,event=event,
            expected_run_version=2,report=report,expected_input_hashes={'case-1':'b'*64},presented={})

    def test_finish_uses_original_finisher_and_returns_after_commit(self):
        args=self.finish_arguments();proof=object()
        with patch.object(module,'finish_signed_skill_eval_with_connection',return_value=proof) as ending:
            self.assertIs(self.owner.finish(SCOPE,**args),proof)
        ending.assert_called_once_with(self.conn,expected_database='fixture_database',scope=SCOPE,**args)
        self.assertEqual(self.conn.events[-2:],['commit','close'])
        self.assertNotIn('SET LOCAL ROLE aos_aip_eval_writer',self.conn.events)

    def test_finish_commit_unknown_and_reconcile_never_repeats_ending(self):
        args=self.finish_arguments();self.conn.fail_commit=True
        with patch.object(module,'finish_signed_skill_eval_with_connection',return_value=object()) as ending:
            with self.assertRaises(module.SkillProducerOutcomeUnknown):self.owner.finish(SCOPE,**args)
        ending.assert_called_once()
        self.conn.fail_commit=False
        with patch.object(module,'reconcile_signed_skill_eval_intent',return_value='original-unknown') as lookup:
            result=self.owner.reconcile_finish(SCOPE,**args)
        self.assertEqual(result,'original-unknown')
        lookup.assert_called_once_with(self.conn,report=args['report'],expected_input_hashes=args['expected_input_hashes'],
            presented=args['presented'],intent_id='intent-1',expected_request_hash='a'*64,
            expected_intent_version=4,expected_run_version=3)
        self.assertEqual(self.writer.call_count,1)

    def test_busy_or_autocommit_writer_refused_without_store_call(self):
        for field,value in [('autocommit',True),('row_factory',None),('info',SimpleNamespace(transaction_status=TransactionStatus.INTRANS))]:
            before=getattr(self.conn,field);setattr(self.conn,field,value)
            with self.assertRaises(ValueError):self.owner.claim_dispatch(SCOPE,self.request)
            setattr(self.conn,field,before)
        self.store.claim.assert_not_called();self.assertNotIn('begin',self.conn.events)

    def test_wrong_readonly_context_never_falls_back_to_writer(self):
        original=self.conn.execute
        def drift(sql,parameters=()):
            if 'current_user AS role' in sql:
                return SimpleNamespace(fetchone=lambda:dict(role='aos_runtime',database_name='fixture_database',org_id='dev-org',project_id='dev-project',
                    isolation='repeatable read',readonly='on'))
            return original(sql,parameters)
        self.conn.execute=drift
        with self.assertRaises(ValueError):self.owner.reconcile_dispatch(SCOPE,self.request)
        self.writer.assert_not_called();self.store.claim.assert_not_called()

    def test_finish_wrong_tenant_is_rejected_before_any_writer(self):
        args=self.finish_arguments()
        args['report']=args['report'].model_copy(update={'tenant':TenantContext(org_id='dev-org',project_id='dev-project')})
        with self.assertRaises(ValueError):self.owner.finish(SCOPE,**args)
        self.writer.assert_not_called()

    def test_readonly_database_alias_drift_refused_before_original_lookup(self):
        self.conn.database='different_database'
        with self.assertRaises(ValueError):self.owner.reconcile_dispatch(SCOPE,self.request)
        self.store.get.assert_not_called();self.writer.assert_not_called()
        args=self.finish_arguments()
        with patch.object(module,'reconcile_signed_skill_eval_intent') as reconcile,self.assertRaises(ValueError):
            self.owner.reconcile_finish(SCOPE,**args)
        reconcile.assert_not_called()

if __name__=='__main__':unittest.main()
