"""Record user-authorized internal development scope through canonical owners."""
import argparse
from datetime import UTC, datetime
import json
from pathlib import Path

from a0v_formal_text_model_renewal import database_connect
from a0v_firstchain_contract_materialize import require_target
from a0v_formal_text_model import SCOPE, MODEL_ID, PRICE_ID, exact
from aos_api.aip_contracts import PlanStep, ResourceRef
from aos_api.aip_model_runtime_store import AipModelRuntimeStore
from aos_api.aip_skill_registry import AipSkillRegistry
from aos_api.aip_task_store import AipTaskStore
from aos_api.aip_task_models import CreateTaskRequest, CreatePlanRevisionRequest, CreateTaskRunRequest
from aos_api.aip_production_contracts import CreateBriefRequest, BuildEvidenceBundleRequest, ExactRevisionRef
from aos_api.aip_production_contract_store import AipProductionContractStore, canonical_hash

ACTOR = 'a0v-internal-development-scope-recorder'
FACTS = ['firstchain.skill.internal-license', 'firstchain.user.development-scope']
AUTHORITY = 'user-session:AOS-AR2-continuous-development'


def require_internal_skills(skills, logic_ids=('D01','D02','D03')):
    allowed = {frozenset(('D01','D02','D03')), frozenset(('S01','P01','C06','A02','G06'))}
    if frozenset(logic_ids) not in allowed or len(logic_ids)!=len(set(logic_ids)):
        raise ValueError('INTERNAL_LICENSE_EXACT_SKILLS_REQUIRED')
    if len(skills)!=len(logic_ids) or {s.skill_id for s in skills}!={'ecommerce.skill.'+x for x in logic_ids}:
        raise ValueError('INTERNAL_LICENSE_EXACT_SKILLS_REQUIRED')
    for s in skills:
        if (s.revision != 2 or s.lifecycle.value != 'published' or s.source_license != 'internal'
                or s.publication_tenant is None
                or (s.publication_tenant.org_id, s.publication_tenant.project_id) != SCOPE.key):
            raise ValueError('INTERNAL_LICENSE_SOURCE_OR_TENANT_INVALID')


def run(database, apply=False, logic_ids=('D01','D02','D03')):
    connect = database_connect(database)
    require_target(connect, database)
    registry = AipSkillRegistry(connect)
    skills = [registry.get_skill('ecommerce.skill.'+x,2) for x in logic_ids]
    require_internal_skills(skills,logic_ids)
    runtime = AipModelRuntimeStore(connect)
    model = runtime.get_model(SCOPE,MODEL_ID)
    runtime.require_model_governance(SCOPE,model,runtime.get_price_snapshot(SCOPE,PRICE_ID))
    refs = [exact('SkillTemplate',s,'skill_id').model_dump(mode='json',by_alias=True) for s in skills]
    facts = {'factIds':FACTS, 'skills':refs, 'sourceLicense':'internal', 'authorizationRef':AUTHORITY,
        'scope':'local internal development and validation', 'commercialLicenseAsserted':False,
        'externalPublicationAuthorized':False, 'providerCalls':0}
    key = 'a0v-internal-license-'+canonical_hash(facts)[:24]
    if not apply:
        return {'outcome':'INTERNAL_LICENSE_PLAN_READY','key':key,'writes':0,'providerCalls':0}
    tasks = AipTaskStore(connect_factory=connect)
    task = tasks.create_task(SCOPE,ACTOR,key,CreateTaskRequest(type='aip.governance',
        title='首链技能内部开发用途核验',description='记录既有内部技能许可和用户开发授权，不代表供应商商用许可或经营结果。',goal=facts))
    with connect(SCOPE) as conn:
        row = conn.execute('SELECT * FROM aip_plan_revision WHERE org_id=%s AND project_id=%s AND task_id=%s ORDER BY revision DESC LIMIT 1',(*SCOPE.key,task.id)).fetchone()
    plan = tasks._plan(row) if row else tasks.create_plan(SCOPE,ACTOR,task.id,key+'-plan',
        CreatePlanRevisionRequest(expected_task_version=task.version,
            steps=[PlanStep(step_key='record-internal-scope',title='核验来源并记录本次内部用途')],
            risk={'providerCalls':0,'externalActions':False}))
    task = tasks.get_task(SCOPE,task.id)
    if plan.approval_status == 'draft':
        plan = tasks.approve_plan(SCOPE,ACTOR,task.id,plan.revision,task.version,plan.content_hash)
    task = tasks.get_task(SCOPE,task.id)
    with connect(SCOPE) as conn:
        row = conn.execute('SELECT * FROM aip_task_run WHERE org_id=%s AND project_id=%s AND task_id=%s ORDER BY created_at DESC LIMIT 1',(*SCOPE.key,task.id)).fetchone()
    task_run = tasks._run(row) if row else tasks.create_run(SCOPE,ACTOR,task.id,key+'-run',
        CreateTaskRunRequest(plan_revision_id=plan.id,expected_task_version=task.version))
    if task_run.status.value == 'queued':
        task = tasks.get_task(SCOPE,task.id)
        result = tasks.start_run(SCOPE,task_run.id,expected_run_version=task_run.version,
            expected_task_version=task.version,actor=ACTOR,idempotency_key=key+'-start')
        task_run = result.run
    if task_run.status.value == 'running':
        with connect(SCOPE) as conn:
            step = conn.execute("SELECT * FROM aip_step_run WHERE org_id=%s AND project_id=%s AND run_id=%s AND step_key='record-internal-scope' ORDER BY attempt DESC LIMIT 1",(*SCOPE.key,task_run.id)).fetchone()
        if not step or step['status'] != 'succeeded':
            require_internal_skills([registry.get_skill(s.skill_id,s.revision) for s in skills],logic_ids)
            if step and step['status']=='running' and step['lease_owner']==ACTOR and step['lease_expires_at']>datetime.now(UTC):
                lease=tasks.heartbeat_step(SCOPE,step['step_run_id'],ACTOR,step['fence'],lease_seconds=300)
            else:
                lease = tasks.claim_step(SCOPE,task_run.id,'record-internal-scope',ACTOR,lease_seconds=300)
            for phase,payload in [('think',{'authorizationRef':AUTHORITY}),('act',{'sourceRefs':refs}),
                    ('verify',{'verifiedInternalLicenseCount':len(skills),'providerCalls':0}),('observe',facts)]:
                tasks.record_step_phase(SCOPE,lease.step_run_id,ACTOR,lease.fence,ACTOR,phase,payload)
            tasks.complete_step(SCOPE,lease.step_run_id,ACTOR,lease.fence,ACTOR)
        tasks.complete_run(SCOPE,task_run.id)
    with connect(SCOPE) as conn:
        evidence = conn.execute("SELECT * FROM aip_evidence WHERE org_id=%s AND project_id=%s AND run_id=%s AND evidence_type='taor.observe' ORDER BY created_at DESC LIMIT 1",(*SCOPE.key,task_run.id)).fetchone()
    if (evidence is None or evidence['payload'].get('stepKey') != 'record-internal-scope'
            or evidence['payload'].get('payload') != facts):
        raise ValueError('INTERNAL_LICENSE_EVIDENCE_MISSING_OR_DRIFTED')
    contracts = AipProductionContractStore(connect)
    brief = contracts.create_brief(SCOPE,ACTOR,key+'-brief',CreateBriefRequest(task_id=task.id,
        brief_type='aip.internal-development.scope',schema_ref=ResourceRef(resource_type='Schema',
            resource_id='InternalDevelopmentScope.v1',revision='1',authority='aip-contract'),spec=facts))
    brief = contracts.get_brief(SCOPE,brief.brief_id)
    if brief.lifecycle.value == 'draft':
        brief = contracts.freeze_brief(SCOPE,ACTOR,brief.brief_id,brief.version,key+'-brief-freeze')
    bundle = contracts.build_evidence_bundle(SCOPE,ACTOR,key+'-bundle',BuildEvidenceBundleRequest(
        brief_ref=ExactRevisionRef(resource_type='TaskBriefRevision',resource_id=brief.brief_id,
            revision=brief.revision,content_hash=brief.content_hash),
        subject_refs=[ResourceRef(resource_type='SkillTemplate',resource_id=s.skill_id,revision=str(s.revision),authority='aip-registry') for s in skills],
        cutoff_at=evidence['freshness_at'],item_refs=[ExactRevisionRef(resource_type='Evidence',
            resource_id=evidence['evidence_id'],revision=1,content_hash=evidence['content_hash'])],
        required_fact_ids=FACTS,marking=['internal','no-secret','no-pii'],license_summary={
            'basis':'existing internal skill licenses and user-authorized local development',
            'authorizationRef':AUTHORITY,'sourceLicense':'internal','allowedUse':'internal development',
            'commercialLicenseAsserted':False,'externalPublicationAuthorized':False}))
    if bundle.coverage.value != 'complete' or bundle.freshness.value != 'fresh':
        raise ValueError('INTERNAL_LICENSE_BUNDLE_NOT_READY')
    return {'database':database,'governanceTaskId':task.id,'governanceRunId':task_run.id,
        'bundleId':bundle.bundle_id,'revision':bundle.revision,'contentHash':bundle.content_hash,
        'coverage':bundle.coverage.value,'freshness':bundle.freshness.value,'providerCalls':0,'businessRuns':0}


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--database-name',required=True)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=run(args.database_name,args.apply)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))
