"""Activate only the data advisor and its three exact first-chain skill bindings."""
import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from a0v_firstchain_capability_bindings import prepare, exact, SCOPE
from a0v_firstchain_capability_activate import latest_health
from aos_api.aip_agent_registry_store import AipAgentRegistryStore
from aos_api.aip_agent_instance_activation_service import AipAgentInstanceActivationService
from aos_api.aip_agent_control_contracts import ActivateAgentInstanceRequest
from aos_api.aip_agent_registry_contracts import CreateSkillBindingRequest, EvaluateOperationalBindingRequest, OperationalBindingDependencies, UpdateSkillBindingRequest
from aos_api.aip_capability_binding_service import AipCapabilityBindingService
from aos_api.aip_skill_registry import AipSkillRegistry

INSTANCE='ecommerce.data_advisor.default'
ACTOR='a0v-firstchain-skill-owner'
ROLE_SKILLS={INSTANCE:('D01','D02','D03'),'ecommerce.customer_service.default':('S01',),
    'ecommerce.private_domain_manager.default':('P01',),'ecommerce.content_officer.default':('C06',),
    'ecommerce.campaign_planner.default':('A02',),'ecommerce.shopping_advisor.default':('G06',)}


def require_template(instance,template,instance_id=INSTANCE):
    if (instance_id not in ROLE_SKILLS or instance.instance_id!=instance_id or template.template_id!=instance_id.removesuffix('.default')
            or template.lifecycle.value!='published' or template.content_hash!=instance.template.content_hash
            or not set(ROLE_SKILLS[instance_id])<=set(template.manifest.get('logicIds',[]))):
        raise ValueError('FIRSTCHAIN_EXACT_ADVISOR_TEMPLATE_REQUIRED')


def run(database):
    connect,readiness,items=prepare(database)
    if len(items)!=3 or {x[0] for x in items}!={'ecommerce.skill.D01','ecommerce.skill.D02','ecommerce.skill.D03'}:
        raise ValueError('FIRSTCHAIN_EXACT_THREE_SKILLS_REQUIRED')
    return bind_items(connect,readiness,items,INSTANCE,database=database)


def bind_items(connect,readiness,items,instance_id,*,database):
    if instance_id not in ROLE_SKILLS or {item[0].rsplit('.',1)[1] for item in items}!=set(ROLE_SKILLS[instance_id]):
        raise ValueError('INVESTIGATION_ROLE_SKILL_MAPPING_INVALID')
    capabilities=AipCapabilityBindingService(connect,readiness_service=readiness)
    by_skill={}
    for skill,request,deps,preview in items:
        if preview.readiness.value!='available':raise ValueError('FIRSTCHAIN_CURRENT_DEPENDENCIES_BLOCKED')
        latest_health(connect,deps.provider_ref)
        binding=capabilities.get(SCOPE,request.binding_id)
        if (binding.status!='active' or binding.health.value!='healthy'
                or binding.capability!=request.binding.capability or binding.dependencies!=deps
                or binding.operational_readiness.value!='available' or binding.readiness_expires_at<=datetime.now(UTC)):
            raise ValueError('FIRSTCHAIN_EXACT_ACTIVE_CAPABILITY_REQUIRED')
        by_skill[skill]=(binding,deps)
    agents=AipAgentRegistryStore(connect)
    instance=agents.get_instance(SCOPE,instance_id)
    template=agents.get_template(instance.template.asset_id,instance.template.revision)
    require_template(instance,template,instance_id)
    if instance.status.value not in {'provisioning','active'}:raise ValueError('FIRSTCHAIN_ADVISOR_STATE_UNSUPPORTED')
    # The original exact transition is replayed when already active.
    instance,_=AipAgentInstanceActivationService(connect_factory=connect,store=agents).activate(SCOPE,instance_id,
        ActivateAgentInstanceRequest(expected_version=1,capability_binding_ids=[by_skill[k][0].binding_id for k in sorted(by_skill)]),
        idempotency_key='a0v-firstchain-advisor-activate-v1' if instance_id==INSTANCE else 'a0v-investigation-'+instance_id+'-activate-v1',actor=ACTOR,occurred_at=datetime.now(UTC))
    registry=AipSkillRegistry(connect)
    results=[]
    for skill_id in sorted(by_skill):
        capability,cap_deps=by_skill[skill_id]
        skill=registry.get_skill(skill_id,2)
        deps=OperationalBindingDependencies(model_route_ref=skill.model_route_ref,runtime_policy_ref=skill.runtime_policy_ref,
            eval_gate_ref=skill.release_gate_ref,budget_policy_ref=cap_deps.budget_policy_ref)
        if deps.model_route_ref!=cap_deps.model_route_ref or deps.runtime_policy_ref!=cap_deps.runtime_policy_ref:
            raise ValueError('FIRSTCHAIN_SKILL_ROUTE_DRIFT')
        request=CreateSkillBindingRequest(binding_id='a0v-firstchain-skill-'+skill_id.rsplit('.',1)[1].lower(),instance_id=instance_id,
            skill=exact('SkillTemplate',skill.skill_id,skill.revision,skill.content_hash),capability_binding_ids=[capability.binding_id],
            budget_policy_ref=deps.budget_policy_ref)
        key=request.binding_id
        binding,_=registry.create_binding(SCOPE,request,idempotency_key=key+'-create',actor=ACTOR,occurred_at=datetime.now(UTC))
        if binding.instance_id!=instance_id or binding.skill!=request.skill or binding.capability_binding_ids!=request.capability_binding_ids:
            raise ValueError('FIRSTCHAIN_SKILL_BINDING_DRIFT')
        if binding.status=='provisioning':
            if binding.dependencies!=deps or binding.readiness.value!='available' or binding.readiness_expires_at is None or binding.readiness_expires_at<=datetime.now(UTC):
                binding,result,_=registry.evaluate_binding(SCOPE,binding.binding_id,
                    EvaluateOperationalBindingRequest(expected_version=binding.version,dependencies=deps),
                    idempotency_key=key+'-evaluate-v'+str(binding.version),actor=ACTOR,evaluated_at=datetime.now(UTC))
                if result.readiness.value!='available':raise ValueError('FIRSTCHAIN_SKILL_NOT_READY:'+','.join(result.reasons))
            binding,_=registry.update_binding(SCOPE,binding.binding_id,
                UpdateSkillBindingRequest(expected_version=binding.version,from_status='provisioning',to_status='active'),
                idempotency_key=key+'-activate',actor=ACTOR,occurred_at=datetime.now(UTC))
        elif binding.status=='active' and binding.dependencies==deps:
            if binding.readiness_expires_at<=datetime.now(UTC):
                binding,result,_=registry.evaluate_binding(SCOPE,binding.binding_id,
                    EvaluateOperationalBindingRequest(expected_version=binding.version,dependencies=deps),
                    idempotency_key=key+'-refresh-v'+str(binding.version),actor=ACTOR,evaluated_at=datetime.now(UTC))
                if result.readiness.value!='available':raise ValueError('FIRSTCHAIN_SKILL_REFRESH_BLOCKED')
        else:
            raise ValueError('FIRSTCHAIN_SKILL_STATE_REVALIDATION_REQUIRED')
        results.append({'skillId':skill_id,'bindingId':binding.binding_id,'status':binding.status,'version':binding.version,
            'readiness':binding.readiness.value,'dependencySnapshotHash':binding.dependency_snapshot_hash,'expiresAt':binding.readiness_expires_at})
    return {'database':database,'instanceId':instance_id,'instanceStatus':instance.status.value,'instanceVersion':instance.version,
        'skillBindings':results,'providerCalls':0,'businessRuns':0,'unboundSkills':['D04','D05','D06'] if instance_id==INSTANCE else []}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--database-name',required=True);parser.add_argument('--apply',action='store_true');parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not args.apply:raise ValueError('FIRSTCHAIN_EXPLICIT_APPLY_REQUIRED')
    result=run(args.database_name)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,default=str,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,default=str,ensure_ascii=False,indent=2))
