"""Real isolated Eval execution; source inventories/contracts remain fixtures."""
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import importlib
import json
import pytest
from aos_api.aip_contracts import PlanStep
from aos_api.aip_task_models import CreateTaskRequest,CreatePlanRevisionRequest,CreateTaskRunRequest
from aos_api.aip_task_store import AipTaskStore
from aos_api.aip_eval_runner import AipEvalRunner,ResolvedArtifact,TargetExecution,compute_eval_report_hash
from aos_api.aip_eval_authority_store import AipEvalAuthorityConflict
from aos_api.aip_eval_pack_registry import AipEvalPackRegistry
from aos_api.aip_eval_contracts import EvalSubjectArtifactRef,EvalStageAttemptRef,EvalGatePolicyRef
from aos_api.aip_agent_text_output import read_agent_text
from test_aip_text_eval_input import helpers
from test_ecommerce_analyst_growth_plan_full_graph import disposable_database,SCOPE
from test_ecommerce_analyst_method_authority import apply_migrations


def stage_attempt(connect,stage):
    store=AipTaskStore(connect)
    task=store.create_task(SCOPE,'tester','structure-task',CreateTaskRequest(type='analysis',title='Isolated single stage structure check'))
    plan=store.create_plan(SCOPE,'tester',task.id,'structure-plan',CreatePlanRevisionRequest(expected_task_version=task.version,steps=[PlanStep(step_key=stage,title=stage)]))
    task=store.get_task(SCOPE,task.id)
    store.approve_plan(SCOPE,'tester',task.id,plan.revision,task.version,plan.content_hash)
    task=store.get_task(SCOPE,task.id)
    run=store.create_run(SCOPE,'tester',task.id,'structure-run',CreateTaskRunRequest(plan_revision_id=plan.id,expected_task_version=task.version))
    store.start_run(SCOPE,run.id,expected_run_version=run.version,expected_task_version=store.timeline(SCOPE,run.id).task.version,actor='tester',idempotency_key='structure-start')
    lease=store.claim_step(SCOPE,run.id,stage,'worker',lease_seconds=60)
    return EvalStageAttemptRef(runId=run.id,stepKey=stage,stepRunId=lease.step_run_id,attempt=lease.attempt,inputHash=lease.input_hash)


@pytest.mark.parametrize('stage',['portrait','diagnosis','solution-design'])
@pytest.mark.parametrize('valid',[True,False])
def test_package_structure_function_forms_real_exact_report(monkeypatch,stage,valid):
    root=Path(__file__).resolve().parents[3]
    monkeypatch.syspath_prepend(str(root/'bundles/solutions/ecommerce-growth/backend'))
    monkeypatch.syspath_prepend(str(Path(__file__).parent/'extension_runtime'))
    fixture=importlib.import_module('test_analyst_structure_eval')
    evaluate=importlib.import_module('ecommerce_growth.analyst_structure_eval').evaluate_structure
    item=fixture.envelope(stage)
    if not valid:
        body=json.loads(item['subjectText']);body['approvedAt']='UNTRUSTED_APPROVAL_MARKER'
        fixture.replace_body(item,body)
    text=item['subjectText'];h=helpers(monkeypatch)
    h.INPUT_VALUE=item['caseInput']
    h.EXPECTED_VALUE=dict(schemaVersion='aos.analyst-structure-result/v1',stage=stage,structurePassed=True,detailCode='STRUCTURE_VALID')
    h.INPUT=h.INPUT.model_copy(update={'content_hash':h._value_hash(h.INPUT_VALUE)})
    h.EXPECTED=h.EXPECTED.model_copy(update={'content_hash':h._value_hash(h.EXPECTED_VALUE)})
    with disposable_database() as connect:
        apply_migrations(connect)
        step=stage_attempt(connect,stage)
        identity=AipTaskStore(connect).record_artifact(SCOPE,step.run_id,'tester','agent_text_output',{'contentHash':sha256(text.encode()).hexdigest(),'marking':['internal']},text_content=text)
        subject=EvalSubjectArtifactRef(resourceId=identity,contentHash=sha256(text.encode()).hexdigest())
        h._seed(AipEvalPackRegistry(connect_factory=connect))
        contract=h._contract().model_copy(update={'gate_policy':{'subjectKind':'agent_text_output','subjectInputMode':'text-envelope-v1'}})
        runner=AipEvalRunner(connect_factory=connect,production_contract_store=SimpleNamespace(get_eval_contract=lambda *args:contract))
        calls=[]
        def resolve(ref):
            if ref.artifact_type!='agent_text_output':return h._resolver(ref)
            with connect(SCOPE) as conn:value=read_agent_text(conn,SCOPE,ref,markings=['internal'])
            return ResolvedArtifact(reference=ref,value=value)
        def target(ref,value):
            calls.append(ref)
            return TargetExecution(target=ref,value=evaluate(value))
        def run():
            return runner.run_by_contract(SCOPE,contract_id=contract.contract_id,contract_revision=contract.revision,contract_content_hash=contract.content_hash,idempotency_key='structure-eval',actor='tester',resolve_artifact=resolve,execute_target=target,execute_judge=h._judge,subject_artifact_ref=subject,stage_attempt_ref=step,gate_policy_ref=EvalGatePolicyRef(resourceId='fixture-policy',revision=1,contentHash='d'*64),evidence_cutoff_at=h.NOW)
        report=run()
        assert report.gate_passed is valid and len(calls)==1
        assert report.subject_artifact_ref==subject and report.stage_attempt_ref==step
        assert report.content_hash==compute_eval_report_hash(report)
        assert runner.get_report(SCOPE,report.report_id)==report
        assert text not in report.model_dump_json() and 'UNTRUSTED_APPROVAL_MARKER' not in report.model_dump_json()
        with pytest.raises(AipEvalAuthorityConflict):run()
        assert len(calls)==1
        with connect(SCOPE) as conn:
            row=conn.execute('SELECT status FROM aip_eval_run WHERE org_id=%s AND project_id=%s AND run_id=%s',(*SCOPE.key,report.run_id)).fetchone()
            assert row['status']=='succeeded'
            assert conn.execute('SELECT count(*) AS n FROM aip_eval_report_revision WHERE org_id=%s AND project_id=%s AND run_id=%s',(*SCOPE.key,report.run_id)).fetchone()['n']==1
