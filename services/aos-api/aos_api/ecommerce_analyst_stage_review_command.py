"""Internal, transaction-bound human stage decisions. No public route or dispatch."""
from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_agent_run_execution_service import AipAgentRunExecutionService
from aos_api.aip_agent_run_service import AipAgentRunService
from aos_api.aip_agent_text_output import read_agent_text
from aos_api.aip_business_investigation_compile_saga import BusinessInvestigationCompilationReceipt, BusinessInvestigationCompilationReceiptStore
from aos_api.aip_eval_authority_store import AipEvalAuthorityStore
from aos_api.aip_eval_contracts import AssetRevisionRef, AssetType, EvalContractRevisionRef, EvalGatePolicyRef, EvalSubjectArtifactRef
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_production_contracts import CreateEvalContractRequest
from aos_api.aip_release_publication_service import AipReleasePublicationService
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef, GrowthPlanRevision
from aos_api.ecommerce_analyst_authority_store import canonical_hash
from aos_api.ecommerce_analyst_growth_plan_sources import require_current_revision
from aos_api.ecommerce_analyst_stage_decision import AnalystStageDecisionRevision
from aos_api.ecommerce_analyst_stage_decision_store import AnalystStageDecisionStore, stage_decision_id
from aos_api.ecommerce_analyst_stage_eval_report import read_stage_eval_report
from aos_api.ecommerce_analyst_stage_review_authority import require_stage_review_authority
from aos_api.ecommerce_analyst_stage_review_runtime import require_stage_review_runtime
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory


def _compiled_responsibility(tx, scope, item):
    rows=tx.execute('''SELECT * FROM aip_business_investigation_compile_receipt
        WHERE org_id=%s AND project_id=%s AND plan_revision_id=%s FOR SHARE''',(*scope.key,item.plan_ref.resource_id)).fetchall()
    if len(rows)!=1:raise ValueError('one original business compilation required')
    row=rows[0]
    compiled=BusinessInvestigationCompilationReceipt.model_validate(row['receipt_data'])
    factory=TransactionBoundConnectFactory(tx,scope)
    reread=BusinessInvestigationCompilationReceiptStore(factory).get_for_run(scope,compiled.run_ref)
    if (reread!=compiled or canonical_hash(row['receipt_data'])!=canonical_hash(compiled.model_dump(mode='json',by_alias=True))
        or compiled.plan_ref.model_dump(mode='json',by_alias=True)!=item.plan_ref.model_dump(mode='json',by_alias=True)
        or compiled.responsibility_plan_ref.model_dump(mode='json',by_alias=True)!=item.responsibility_plan_ref.model_dump(mode='json',by_alias=True)
        or row['task_id']!=compiled.task_id or row['plan_revision']!=item.plan_ref.revision
        or row['plan_content_hash']!=item.plan_ref.content_hash or row['receipt_id']!=compiled.receipt_id
        or row['command_id']!=compiled.command_id or row['request_hash']!=compiled.request_hash
        or row['run_id']!=compiled.run_ref.resource_id or row['run_version']!=compiled.run_ref.revision
        or row['run_content_hash']!=compiled.run_ref.content_hash):
        raise ValueError('stage responsibility differs from original compilation')
    run=tx.execute('SELECT task_id,plan_revision_id FROM aip_task_run WHERE org_id=%s AND project_id=%s AND run_id=%s FOR SHARE',(*scope.key,item.task_run_id)).fetchone()
    if run is None or run['task_id']!=compiled.task_id or run['plan_revision_id']!=item.plan_ref.resource_id:
        raise ValueError('stage run differs from original compilation')


def _subject(tx,scope,ref):
    if ref.resource_type!='GrowthPlanRevision':return require_current_revision(tx,scope,ref)
    row=tx.execute('''SELECT revision.payload,revision.content_hash FROM ecommerce_analyst_growth_plan_head head
        JOIN ecommerce_analyst_growth_plan_revision revision ON revision.org_id=head.org_id
        AND revision.project_id=head.project_id AND revision.plan_id=head.plan_id AND revision.revision=head.current_revision
        WHERE head.org_id=%s AND head.project_id=%s AND head.plan_id=%s AND head.current_revision=%s FOR SHARE OF head''',(*scope.key,ref.resource_id,ref.revision)).fetchone()
    if row is None:raise ValueError('current growth draft unavailable')
    result=GrowthPlanRevision.model_validate(row['payload'])
    if (result.lifecycle!='draft' or result.plan_id!=ref.resource_id or result.revision!=ref.revision
        or (result.tenant.org_id,result.tenant.project_id)!=scope.key or result.content_hash!=ref.content_hash
        or row['content_hash']!=ref.content_hash
        or canonical_hash(result.model_dump(mode='json',by_alias=True,exclude={'content_hash'}))!=ref.content_hash
        or canonical_hash(row['payload'])!=canonical_hash(result.model_dump(mode='json',by_alias=True))):
        raise ValueError('current growth draft body drifted')
    return result


def _sources_and_eval(tx,scope,item,plan,markings):
    factory=TransactionBoundConnectFactory(tx,scope)
    subject=_subject(tx,scope,item.subject_ref)
    if subject.generation_artifact_ref!=item.artifact_ref or item.artifact_ref.revision!=1:
        raise ValueError('stage subject does not bind original generation artifact')
    insight=subject
    if item.stage=='solution-design':insight=_subject(tx,scope,subject.decision_ref)
    if item.stage!='portrait':insight=_subject(tx,scope,insight.insight_ref)
    artifact=tx.execute('SELECT run_id,source FROM aip_artifact WHERE org_id=%s AND project_id=%s AND artifact_id=%s FOR SHARE',(*scope.key,item.artifact_ref.resource_id)).fetchone()
    if artifact is None or artifact['run_id']!=item.task_run_id or not isinstance(artifact['source'],dict):
        raise ValueError('original stage artifact is not in this run')
    source=artifact['source']
    if not source.get('attemptId') or not source.get('agentRunId'):raise ValueError('original generation provenance missing')
    attempt=AipAgentRunExecutionService(factory).get(scope,source['attemptId'])
    agent=AipAgentRunService(factory).get(scope,source['agentRunId'])
    original=attempt.output_artifact_ref
    now=tx.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    if (attempt.agent_run_id!=agent.agent_run_id or agent.task_run_id!=item.task_run_id or attempt.status!='succeeded'
        or attempt.reason_code is not None or not attempt.provider_receipt_id or not attempt.usage_receipt_ids
        or attempt.completed_at is None or not subject.created_at==attempt.completed_at<=now
        or attempt.created_by!=subject.created_by or original is None
        or original.artifact_id!=item.artifact_ref.resource_id or original.content_hash!=item.artifact_ref.content_hash
        or agent.request.skill.asset_type!='SkillTemplate'
        or agent.request.model_route!=attempt.route_ref or agent.request.policy!=attempt.policy_ref
        or agent.request.skill.asset_id!={'portrait':'ecommerce.skill.D01','diagnosis':'ecommerce.skill.D02','solution-design':'ecommerce.skill.D03'}[item.stage]):
        raise ValueError('stage generation is not proven successful in this run')
    read_agent_text(tx,scope,original,markings=markings)
    # The approved Plan owns the stage's exact Eval contract; no caller-selected fallback.
    step=next(step for step in plan['steps'] if step['stepKey']==item.stage)
    refs=[AnalystExactRef.model_validate(ref) for ref in step.get('gateRefs',[]) if ref.get('resourceType')=='EvalContractRevision']
    if len(refs)!=1:raise ValueError('approved stage must declare one exact EvalContract')
    ref=refs[0]
    head=tx.execute('SELECT current_revision FROM aip_eval_contract_head WHERE org_id=%s AND project_id=%s AND contract_id=%s FOR SHARE',(*scope.key,ref.resource_id)).fetchone()
    if head is None or head['current_revision']!=ref.revision:raise ValueError('stage EvalContract is not current')
    contract=AipProductionContractStore(factory).get_eval_contract(scope,ref.resource_id,ref.revision,conn=tx)
    body=CreateEvalContractRequest(**{field:getattr(contract,field) for field in CreateEvalContractRequest.model_fields})
    if (contract.content_hash!=ref.content_hash or canonical_hash(body.model_dump(mode='json',by_alias=True))!=ref.content_hash
        or contract.lifecycle!='frozen' or contract.readiness!='ready' or contract.blockers
        or contract.gate_policy.get('subjectKind')!='agent_text_output'
        or contract.gate_policy.get('subjectInputMode')!='text-envelope-v1'
        or (item.stage=='portrait' and insight.eval_ref!=ref) or contract.release_gate_ref is None):
        raise ValueError('stage EvalContract is not an effective text contract')
    policy=EvalGatePolicyRef.model_validate(contract.gate_policy.get('stagePolicyRef'))
    gate_ref=contract.release_gate_ref
    tx.execute('SELECT decision_id FROM aip_release_gate_decision WHERE org_id=%s AND project_id=%s AND decision_id=%s FOR SHARE',(*scope.key,gate_ref.resource_id)).fetchone()
    gate=AipEvalAuthorityStore(factory).require_exact_passed(scope,VersionedAssetRef(assetType='EvalGateDecision',assetId=gate_ref.resource_id,revision=gate_ref.revision,contentHash=gate_ref.content_hash),now=now)
    if gate.invalidated_by is not None:raise ValueError('stage Eval release gate invalidated')
    AipReleasePublicationService._verify_gate_evidence(tx,scope,gate)
    report=read_stage_eval_report(tx,scope,item.eval_report_ref,
        artifact_ref=EvalSubjectArtifactRef(resourceId=item.artifact_ref.resource_id,contentHash=item.artifact_ref.content_hash),
        stage_attempt_ref=item.stage_attempt_ref,eval_contract_ref=EvalContractRevisionRef(resourceId=ref.resource_id,revision=ref.revision,contentHash=ref.content_hash),
        gate_policy_ref=policy,cutoff_at=insight.cutoff_at)
    expected_target=AssetRevisionRef(assetType=AssetType.SKILL_TEMPLATE,assetId=agent.request.skill.asset_id,
        revision=str(agent.request.skill.revision),contentHash=agent.request.skill.content_hash)
    if (report.created_at<attempt.completed_at or report.suite_ref.asset_id!=contract.suite_ref.resource_id
        or report.suite_ref.revision!=str(contract.suite_ref.revision) or report.suite_ref.content_hash!=contract.suite_ref.content_hash
        or report.target!=expected_target):
        raise ValueError('stage report predates generation or uses a different suite or target')


class AnalystStageReviewCommandService:
    def __init__(self,connect_factory):
        if not callable(connect_factory):raise TypeError('explicit scoped connection factory required')
        self.connect=connect_factory

    def decide(self,scope,item,*,actor,key,expected_version,markings):
        item=AnalystStageDecisionRevision.model_validate(item.model_dump())
        if (item.created_by!=actor or (item.tenant.org_id,item.tenant.project_id)!=scope.key
            or item.decision_id!=stage_decision_id(item) or type(key) is not str or not key or key.strip()!=key or len(key)>200
            or type(expected_version) is not int or expected_version<0
            or canonical_hash(item.model_dump(mode='json',by_alias=True,exclude={'content_hash'}))!=item.content_hash):
            raise ValueError('stage decision command identity drifted')
        with self.connect(scope) as conn:
            tx=HostTransaction(conn);owner=AnalystStageDecisionStore(tx,scope)
            for lock in sorted({canonical_hash([*scope.key,'stage-target',item.decision_id]),canonical_hash([*scope.key,'stage-key',key])}):
                tx.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(lock,))
            reviewer=require_stage_review_authority(tx,scope,responsibility_plan_ref=item.responsibility_plan_ref,stage=item.stage,actor=actor)
            if reviewer!=item.reviewer:raise ValueError('reviewer differs from current responsibility')
            replay=tx.execute('''SELECT result_ref FROM ecommerce_analyst_authority_receipt
                WHERE org_id=%s AND project_id=%s AND operation='analyst.stage_decision_publish' AND idempotency_key=%s''',(*scope.key,key)).fetchone()
            if replay is not None:
                ref=AnalystExactRef.model_validate(replay['result_ref'])
                if owner.read_exact(ref)!=item or expected_version!=item.version-1:raise ValueError('stage review replay command drifted')
                return ref
            _compiled_responsibility(tx,scope,item)
            if item.decision=='revoke':
                if item.prior_ref is None:raise ValueError('revoke requires current prior decision')
                owner.read_current(item.prior_ref)
            else:
                plan=require_stage_review_runtime(tx,scope,**{key:getattr(item,key) for key in ('task_run_id','plan_ref','stage','stage_attempt_ref','subject_ref')})
                _sources_and_eval(tx,scope,item,plan,list(markings))
            now=tx.execute('SELECT clock_timestamp() AS now').fetchone()['now']
            if item.created_at>now or (item.decision=='accept' and item.expires_at<=now):raise ValueError('stage decision is not effective now')
            return owner.put(item,actor=actor,key=key,expected_version=expected_version)
