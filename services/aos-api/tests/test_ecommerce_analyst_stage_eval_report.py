from datetime import timedelta
import pytest
from aos_api.aip_eval_authority_store import AipEvalAuthorityStore
from aos_api.aip_eval_contracts import EvalRunAuthorityRecord,EvalRunEvent
from aos_api.aip_eval_runner import AipEvalRunner,compute_eval_report_hash
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.ecommerce_analyst_stage_eval_report import read_stage_eval_report
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.tenant_scope import TenantScope
from test_ecommerce_analyst_growth_plan_full_graph import disposable_database,SCOPE
from test_aip_business_investigation_eval import request,report


def seed(conn,*,identity='first',passed=True,finish=True,offset=0):
    now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']-timedelta(minutes=5)+timedelta(seconds=offset)
    item=report(request(),gate_passed=passed).model_copy(update={'report_id':identity,'run_id':'eval-'+identity,'created_at':now+timedelta(seconds=2)})
    item=item.model_copy(update={'content_hash':compute_eval_report_hash(item)})
    factory=TransactionBoundConnectFactory(HostTransaction(conn),SCOPE)
    owner=AipEvalAuthorityStore(factory)
    fields=('tenant','run_id','suite_ref','eval_contract_ref','subject_artifact_ref','stage_attempt_ref','gate_policy_ref','evidence_cutoff_at','target','dataset','judge')
    record=EvalRunAuthorityRecord(**{f:getattr(item,f) for f in fields},status='queued',idempotencyKey=identity,createdBy='tester',createdAt=now,version=1)
    def event(n,before,after):
        return EvalRunEvent(tenant=item.tenant,eventId=identity+str(n),runId=item.run_id,sequence=n,eventType='status_changed',
            fromStatus=before,toStatus=after,payloadHash='a'*64,actor='tester',createdAt=now+timedelta(seconds=n-1 if n<3 else 3))
    owner.create_eval_run(SCOPE,record,event(1,None,'queued'))
    owner.transition_eval_run(SCOPE,event(2,'queued','running'),expected_version=1)
    AipEvalRunner(connect_factory=factory)._append_report(SCOPE,item)
    if finish:owner.transition_eval_run(SCOPE,event(3,'running','succeeded'),expected_version=2)
    return item


def check(conn,item,**changes):
    args=dict(artifact_ref=item.subject_artifact_ref,stage_attempt_ref=item.stage_attempt_ref,eval_contract_ref=item.eval_contract_ref,
        gate_policy_ref=item.gate_policy_ref,cutoff_at=item.evidence_cutoff_at)
    ref=changes.pop('ref',AnalystExactRef(resourceType='EvalReportRevision',resourceId=item.report_id,revision=item.revision,contentHash=item.content_hash))
    scope=changes.pop('scope',SCOPE)
    args.update(changes)
    return read_stage_eval_report(HostTransaction(conn),scope,ref,**args)


def test_actual_successful_execution_and_every_exact_binding():
    with disposable_database() as connect:
        with connect(SCOPE) as conn:
            item=seed(conn)
            assert check(conn,item)==item
            for field in ('artifact_ref','stage_attempt_ref','eval_contract_ref','gate_policy_ref'):
                value=getattr(item,'subject_artifact_ref' if field=='artifact_ref' else field)
                changed=value.model_copy(update={'input_hash' if field=='stage_attempt_ref' else 'content_hash':'9'*64})
                with pytest.raises(ValueError,match='inputs drifted'):check(conn,item,**{field:changed})
            with pytest.raises(ValueError):check(conn,item,cutoff_at=item.evidence_cutoff_at+timedelta(seconds=1))
            with pytest.raises(ValueError):check(conn,item,scope=TenantScope('dev-org','dev-project'))
            with pytest.raises(ValueError):check(conn,item,ref=AnalystExactRef(resourceType='EvalReportRevision',resourceId=item.report_id,revision=1,contentHash='b'*64))


def test_new_failed_report_supersedes_old_pass():
    with disposable_database() as connect:
        with connect(SCOPE) as conn:
            first=seed(conn)
            second=seed(conn,identity='second',passed=False,offset=10)
            with pytest.raises(ValueError,match='no longer latest'):check(conn,first)
            with pytest.raises(ValueError,match='valid passed'):check(conn,second)


def test_report_without_successful_run_does_not_authorize():
    with disposable_database() as connect:
        with connect(SCOPE) as conn:
            item=seed(conn,finish=False)
            with pytest.raises(RuntimeError,match='did not succeed'):check(conn,item)


def test_actual_report_hash_detects_modified_body():
    with disposable_database() as connect:
        with connect(SCOPE) as conn:
            item=seed(conn)
            # Immutable DB prevents tampering: simulate a corrupt row only at read boundary.
            class Corrupt:
                def execute(self,sql,params=None):
                    cursor=conn.execute(sql,params)
                    if 'SELECT * FROM aip_eval_report_revision' in sql:
                        row=dict(cursor.fetchone());row['results']=[{**result,'detailCode':'DRIFT'} for result in row['results']]
                        from types import SimpleNamespace
                        return SimpleNamespace(fetchone=lambda:row)
                    return cursor
            with pytest.raises(ValueError):
                ref=AnalystExactRef(resourceType='EvalReportRevision',resourceId=item.report_id,revision=1,contentHash=item.content_hash)
                read_stage_eval_report(HostTransaction(Corrupt()),SCOPE,ref,artifact_ref=item.subject_artifact_ref,
                    stage_attempt_ref=item.stage_attempt_ref,eval_contract_ref=item.eval_contract_ref,gate_policy_ref=item.gate_policy_ref,cutoff_at=item.evidence_cutoff_at)
