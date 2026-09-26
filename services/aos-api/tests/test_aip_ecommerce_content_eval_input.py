"""A current readable content Artifact is the evaluated subject, not a loose report."""

from pathlib import Path
import importlib.util
from types import SimpleNamespace

import pytest

from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.aip_contracts import ExactContractRef, PlanStep
from aos_api.aip_eval_contracts import EvalSubjectArtifactRef, EvalStageAttemptRef, EvalGatePolicyRef
from aos_api.aip_eval_authority_store import AipEvalAuthorityConflict
from aos_api.aip_eval_pack_registry import AipEvalPackRegistry
from aos_api.aip_eval_runner import AipEvalRunner
from aos_api.aip_task_models import CreateTaskRequest, CreatePlanRevisionRequest, CreateTaskRunRequest
from aos_api.aip_task_store import AipTaskStore
from aos_api.aip_production_contract_store import AipProductionContractStore, ProductionContractDependencyBlocked
from aos_api.aip_production_contracts import (CreateReviewIssueRequest, ExactArtifactRef,
    ExactRevisionRef, RegisterReviewRuleRevisionRequest)
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import ContentReviewHostService
from test_ecommerce_analyst_growth_plan_full_graph import disposable_database, SCOPE
from test_ecommerce_analyst_method_authority import apply_migrations


def _helpers():
    path=Path(__file__).parent/'aip/test_aip_eval_runner.py'
    spec=importlib.util.spec_from_file_location('content_eval_fixture_helpers',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SCOPE=SCOPE
    return module


def test_exact_content_artifact_runs_governed_eval_without_body_in_report():
    helper=_helpers()
    with disposable_database() as connect:
        apply_migrations(connect)
        migration_path=Path(__file__).resolve().parents[1]/'alembic/versions/a0v_105_content_eval_contract_policy_ref.py'
        migration_spec=importlib.util.spec_from_file_location('content_eval_policy_migration',migration_path)
        migration=importlib.util.module_from_spec(migration_spec)
        migration_spec.loader.exec_module(migration)
        with connect(SCOPE) as conn:
            migration.op=SimpleNamespace(execute=conn.execute)
            migration.upgrade()
        contract=helper._contract().model_copy(update={'gate_policy':{
            'subjectKind':'ecommerce_content','subjectInputMode':'ecommerce-readable-content/v1'}})
        store=AipTaskStore(connect)
        task=store.create_task(SCOPE,'tester','content-eval-task',CreateTaskRequest(type='analysis',title='Content eval'))
        plan=store.create_plan(SCOPE,'tester',task.id,'content-eval-plan',
            CreatePlanRevisionRequest(expected_task_version=task.version,
                steps=[PlanStep(step_key='content_generate',title='Generate content'),
                    PlanStep(step_key='content_review',title='Review content',gate_refs=[
                        ExactContractRef(resourceType='EvalContractRevision',
                            resourceId=contract.contract_id,revision=contract.revision,
                            contentHash=contract.content_hash)])]))
        task=store.get_task(SCOPE,task.id)
        store.approve_plan(SCOPE,'tester',task.id,plan.revision,task.version,plan.content_hash)
        task=store.get_task(SCOPE,task.id)
        run=store.create_run(SCOPE,'tester',task.id,'content-eval-run',
            CreateTaskRunRequest(plan_revision_id=plan.id,expected_task_version=task.version))
        store.start_run(SCOPE,run.id,expected_run_version=run.version,
            expected_task_version=store.timeline(SCOPE,run.id).task.version,
            actor='tester',idempotency_key='content-eval-start')
        lease=store.claim_step(SCOPE,run.id,'content_generate','worker',lease_seconds=60)
        identity='artifact-'+'a'*20
        ref=lambda kind,name:dict(resourceType=kind,resourceId=name,revision=1,contentHash='sha256:'+'a'*64)
        content=dict(taskRef=ref('Task',task.id),briefRef=ref('TaskBriefRevision','brief'),
            growthPlanRef=ref('GrowthPlanRevision','plan'),
            sourceArtifactRefs=[ref('ArtifactRevision',str(n)) for n in range(4)],
            factSourceRefs=[ref('EvidenceBundleRevision','facts')],
            body='玫瑰面霜草稿，仅作人工评审，不声称库存或销量。',
            productNames=['玫瑰面霜'],channels=['微信小店'],constraintChecks=['库存待核'])
        digest=canonical_hash(content)
        content['artifactRef']={'resourceType':'ArtifactRevision','resourceId':identity,
            'revision':1,'contentHash':'sha256:'+digest}
        assert store.record_artifact(SCOPE,run.id,'tester','ecommerce_content',
            {'contentHash':digest,'schemaRef':'aos://schemas/ecommerce-readable-content/v1',
             'metadata':{'ecommerceGrowthContentArtifact':content}},artifact_id=identity)==identity
        subject=EvalSubjectArtifactRef(resourceId=identity,contentHash=digest)
        attempt=EvalStageAttemptRef(runId=run.id,stepKey='content_generate',
            stepRunId=lease.step_run_id,attempt=lease.attempt,inputHash=lease.input_hash)
        helper._seed(AipEvalPackRegistry(connect_factory=connect))
        runner=AipEvalRunner(connect_factory=connect,
            production_contract_store=SimpleNamespace(get_eval_contract=lambda *args:contract))
        with pytest.raises(AipEvalAuthorityConflict,match='succeeded'):
            runner._assert_media_subject(SCOPE,subject,attempt,subject_kind='ecommerce_content')
        for phase,payload in (
            ('think',{'kind':'settled_content_reconciliation'}),
            ('act',{'kind':'already_completed_provider_result'}),
            ('verify',{'passed':True}),
            ('observe',{'artifactRef':content['artifactRef']}),
        ):
            store.record_step_phase(SCOPE,lease.step_run_id,'worker',lease.fence,'tester',phase,payload)
        store.complete_step(SCOPE,lease.step_run_id,'worker',lease.fence,'tester')
        policy=EvalGatePolicyRef(resourceType='EvalContractRevision',
            resourceId=contract.contract_id,revision=contract.revision,
            contentHash=contract.content_hash)
        received=[]
        def target(ref,value):
            received.append(value)
            assert value['schemaVersion']=='aos.eval-ecommerce-content-input/v1'
            assert value['subjectArtifactRef']==subject.model_dump(mode='json',by_alias=True)
            assert value['content']==content
            return helper._target(ref,value['caseInput'])
        with pytest.raises(AipEvalAuthorityConflict,match='content gate policy'):
            runner.run_by_contract(SCOPE,contract_id=contract.contract_id,
                contract_revision=contract.revision,contract_content_hash=contract.content_hash,
                idempotency_key='content-subject-eval',actor='tester',resolve_artifact=helper._resolver,
                execute_target=target,execute_judge=helper._judge,subject_artifact_ref=subject,
                stage_attempt_ref=attempt,gate_policy_ref=EvalGatePolicyRef(
                    resourceId='fixture-policy',revision=1,contentHash='d'*64),
                evidence_cutoff_at=helper.NOW)
        report=runner.run_by_contract(SCOPE,contract_id=contract.contract_id,
            contract_revision=contract.revision,contract_content_hash=contract.content_hash,
            idempotency_key='content-subject-eval',actor='tester',resolve_artifact=helper._resolver,
            execute_target=target,execute_judge=helper._judge,subject_artifact_ref=subject,
            stage_attempt_ref=attempt,gate_policy_ref=policy,
            evidence_cutoff_at=helper.NOW)
        assert report.gate_passed and len(received)==1
        assert report.subject_artifact_ref==subject
        assert content['body'] not in report.model_dump_json()
        assert runner.get_report(SCOPE,report.report_id)==report

        contracts=AipProductionContractStore(connect_factory=connect)
        rule=contracts.register_review_rule_revision(SCOPE,'tester','content-review-rule',
            RegisterReviewRuleRevisionRequest(ruleId='content-review-rule',revision=1,
                spec={'subjectKind':'ecommerce_content','checks':['facts','prohibited_claims']}))
        request=CreateReviewIssueRequest(
            ruleRef=ExactRevisionRef(resourceType='EvalRuleRevision',resourceId=rule.rule_id,
                revision=rule.revision,contentHash=rule.content_hash),severity='warning',
            artifactRef=ExactArtifactRef(artifactId=identity,contentHash=digest),
            evalReportRef=ExactRevisionRef(resourceType='EvalReportRevision',
                resourceId=report.report_id,revision=report.revision,contentHash=report.content_hash),
            location={'stage':'content_generate'},suggestedFix='请人工核对内容事实',
            returnStage='content_generate')
        issue=contracts.create_review_issue(SCOPE,'tester','content-issue',request)
        assert issue.artifact_ref.artifact_id==identity
        with connect(SCOPE) as transaction:
            transaction.execute("UPDATE aip_step_run SET status='running' WHERE org_id=%s AND project_id=%s AND step_run_id=%s",
                (*SCOPE.key,lease.step_run_id))
            with pytest.raises(ProductionContractDependencyBlocked,match='ATTEMPT'):
                AipProductionContractStore._require_content_eval_subject(
                    transaction,SCOPE,request.artifact_ref,request.eval_report_ref)
            transaction.rollback()
        with connect(SCOPE) as transaction:
            ContentReviewHostService._issue_eval_authority(
                HostTransaction(transaction),SCOPE,{'decision':'ACCEPT'},issue)
        other_identity='artifact-'+'b'*20
        other_content={**content,'artifactRef':{**content['artifactRef'],'resourceId':other_identity}}
        store.record_artifact(SCOPE,run.id,'tester','ecommerce_content',
            {'contentHash':digest,'schemaRef':'aos://schemas/ecommerce-readable-content/v1',
             'metadata':{'ecommerceGrowthContentArtifact':other_content}},artifact_id=other_identity)
        unrelated=request.model_copy(update={'artifact_ref':ExactArtifactRef(
            artifactId=other_identity,contentHash=digest)})
        with pytest.raises(ProductionContractDependencyBlocked,match='CONTENT_EVAL_SUBJECT'):
            contracts.create_review_issue(SCOPE,'tester','unrelated-content-issue',unrelated)


def test_content_review_issue_rejects_report_with_media_policy_alias():
    artifact=ExactArtifactRef(artifactId='content-1',contentHash='a'*64)
    contract={'resourceType':'EvalContractRevision','resourceId':'contract-1',
        'revision':1,'contentHash':'b'*64}
    report={'subject_artifact_ref':{'resourceType':'Artifact',
        'resourceId':artifact.artifact_id,'contentHash':artifact.content_hash},
        'stage_attempt_ref':{'resourceType':'StepRunAttempt','runId':'run-1',
            'stepKey':'content_generate','stepRunId':'step-1','attempt':1,
            'inputHash':'c'*64},
        'eval_contract_ref':contract,
        'gate_policy_ref':{'resourceType':'MediaGatePolicyRevision',
            'resourceId':'fixture-policy','revision':1,'contentHash':'d'*64}}

    class Result:
        def __init__(self,row): self.row=row
        def fetchone(self): return self.row

    class Conn:
        def execute(self,query,*_):
            if 'FROM aip_artifact' in query:
                return Result({'artifact_type':'ecommerce_content','run_id':'run-1'})
            if 'FROM aip_eval_report_revision' in query:
                return Result(report)
            raise AssertionError('policy drift must fail before StepRun lookup')

    with pytest.raises(ProductionContractDependencyBlocked,match='CONTENT_EVAL_SUBJECT_MISMATCH'):
        AipProductionContractStore._require_content_eval_subject(
            Conn(),SCOPE,artifact,ExactRevisionRef(resourceType='EvalReportRevision',
                resourceId='report-1',revision=1,contentHash='e'*64))
