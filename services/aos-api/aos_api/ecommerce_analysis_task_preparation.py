"""Task and intent Brief preparation; authorization and commit belong to outer Host."""
from aos_api.aip_business_investigation_compiler import BusinessInvestigationTaskBriefIntentSpec
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_production_contracts import CreateBriefRequest, ExactRevisionRef
from aos_api.aip_production_contract_store import AipProductionContractStore, canonical_hash
from aos_api.aip_task_models import CreateTaskRequest
from aos_api.aip_task_store import AipTaskStore
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_business_investigation_case import BusinessInvestigationCaseRevision
from aos_api.ecommerce_business_investigation_run import BusinessInvestigationRunView, BusinessInvestigationRunStore
from aos_api.ecommerce_business_investigation_profile_catalog import EcommerceInvestigationProfileRevision
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.tenant_scope import TenantScope


def prepare_analysis_task(transaction, *, scope, actor, case, run, domain_profile, selection_ref):
    if (type(transaction) is not HostTransaction or type(scope) is not TenantScope
            or type(case) is not BusinessInvestigationCaseRevision or type(run) is not BusinessInvestigationRunView
            or type(domain_profile) is not EcommerceInvestigationProfileRevision
            or type(selection_ref) is not PipelineExactRef
            or selection_ref.resource_type != 'SourceSelectionRevision'
            or type(actor) is not str or not actor or actor != actor.strip()):
        raise ValueError('exact Host analysis preparation inputs required')
    case = BusinessInvestigationCaseRevision.model_validate(case.model_dump(mode='json',by_alias=True))
    run = BusinessInvestigationRunView.model_validate(run.model_dump(mode='json',by_alias=True))
    domain = EcommerceInvestigationProfileRevision.model_validate(domain_profile.model_dump(mode='json',by_alias=True))
    authority,state = run.authority,run.state
    if (any((tenant.org_id,tenant.project_id)!=scope.key for tenant in (case.tenant,authority.tenant,state.tenant))
            or case.lifecycle.value!='ACTIVE' or case.calculated_content_hash()!=case.content_hash
            or authority.calculated_content_hash()!=authority.content_hash
            or state.run_id!=authority.run_id
            or state.lifecycle.value!='PREPARING' or state.control.value!='RUNNING'
            or case.investigation_profile_ref!=domain.exact_ref or case.analysis_type.value!=domain.analysis_type
            or authority.analysis_type!=case.analysis_type
            or (authority.case_ref.resource_id,authority.case_ref.revision,authority.case_ref.content_hash)
                !=(case.case_id,case.revision,case.content_hash)):
        raise ValueError('current analysis intent or Case/Run lineage differs')
    def exact(kind,identity,revision,digest):
        return ExactRevisionRef(resourceType=kind,resourceId=identity,revision=revision,
                                contentHash=digest.removeprefix('sha256:'))
    spec = BusinessInvestigationTaskBriefIntentSpec(
        schemaVersion='aos.aip.business-investigation-task-brief-intent/v2',
        caseRef=exact('BusinessInvestigationCaseRevision',case.case_id,case.revision,case.content_hash),
        runRef=exact('BusinessInvestigationRun',authority.run_id,authority.version,authority.content_hash),
        domainProfileRef=exact('InvestigationProfileRevision',domain.profile_id,domain.revision,domain.content_hash),
        analysisType=domain.analysis_type,compilerProfile=domain.responsibility_template_code)
    spec_json = spec.model_dump(mode='json',by_alias=True)
    key = 'analysis-task-' + canonical_sha256([*scope.key,authority.run_id]).removeprefix('sha256:')
    factory = TransactionBoundConnectFactory(transaction,scope)
    if BusinessInvestigationRunStore(factory).get_verified(scope,authority.run_id)!=run:
        raise ValueError('analysis Run differs from current stored authority')
    tasks = AipTaskStore(factory)
    task_request = CreateTaskRequest(type='ecommerce.business-investigation',title=domain.display_name,
        description='根据原始数据与来源完成经营画像、问题诊断和方案设计。',goal=spec_json,
        selectionRef=ResourceRef(resourceType='SourceSelectionRevision',
            resourceId=selection_ref.resource_id,revision=str(selection_ref.revision),authority='postgresql'))
    task = tasks.create_task(scope,actor,key,task_request)
    if (task.goal!=spec_json or task.type!=task_request.type or task.title!=task_request.title
            or task.selection_ref!=task_request.selection_ref
            or task.status.value!='pending' or task.current_plan_revision_id is not None):
        raise ValueError('analysis task intent or lifecycle drifted')
    contracts = AipProductionContractStore(factory)
    brief_request = CreateBriefRequest(taskId=task.id,briefType='ecommerce.business-investigation.intent',
        schemaRef=ResourceRef(resourceType='JsonSchema',resourceId='aos.aip.business-investigation-task-brief-intent',
            revision='2',authority='aos.aip'),spec=spec_json)
    expected_hash = canonical_hash(dict(briefType=brief_request.brief_type,
        schemaRef=brief_request.schema_ref.model_dump(mode='json',by_alias=True),spec=spec_json))
    brief = contracts.create_brief(scope,actor,key+'-brief-create',brief_request)
    brief = contracts.get_brief(scope,brief.brief_id,conn=transaction)
    if brief.task_id!=task.id or brief.content_hash!=expected_hash or brief.spec!=spec_json:
        raise ValueError('analysis Brief intent drifted')
    if brief.lifecycle.value=='draft':
        brief = contracts.freeze_brief(scope,actor,brief.brief_id,brief.version,key+'-brief-freeze')
    if brief.lifecycle.value!='frozen':
        raise ValueError('analysis Brief is not frozen')
    return dict(task=task.model_dump(mode='json',by_alias=True),taskBriefSpec=spec_json,
        taskBriefRef=exact('TaskBriefRevision',brief.brief_id,brief.revision,brief.content_hash).model_dump(mode='json',by_alias=True))
