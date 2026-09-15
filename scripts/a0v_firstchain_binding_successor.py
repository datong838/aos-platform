"""Explicit eight-skill successor, using canonical binding owners only."""
from datetime import UTC,datetime
from a0v_firstchain_capability_bindings import prepare_material,exact,SCOPE
from a0v_firstchain_capability_activate import latest_health
from a0v_firstchain_skill_bindings import ROLE_SKILLS
from a0v_qyh_current_product_event_first_chain import freeze
from aos_api.aip_capability_binding_service import AipCapabilityBindingService
from aos_api.aip_skill_registry import AipSkillRegistry
from aos_api.aip_agent_registry_contracts import (
    EvaluateOperationalBindingRequest,UpdateCapabilityBindingRequest,
    CreateSkillBindingRequest,OperationalBindingDependencies,UpdateSkillBindingRequest,
)

LOGICS=('D01','D02','D03','S01','P01','C06','A02','G06')
ACTOR='a0v-model-successor-binding-owner'


def serial(value):
    if hasattr(value,'model_dump'):return value.model_dump(mode='json',by_alias=True)
    if isinstance(value,(tuple,list)):return [serial(x) for x in value]
    if isinstance(value,dict):return {k:serial(v) for k,v in value.items()}
    return value


def step(state,key,request,execute):
    intent=state/(key+'-intent.json')
    if intent.exists():raise ValueError('existing binding intent requires read-only receipt inspection')
    freeze(intent,serial(request))
    result=execute()
    freeze(state/(key+'-result.json'),dict(result=serial(result)))
    return result


def skill_proof(publication):
    rows=publication['skills']
    result={r['skill']['asset_id']:r['skill'] for r in rows}
    if (len(rows)!=8 or len(result)!=8 or set(result)!={'ecommerce.skill.'+x for x in LOGICS}
        or any(x['revision']!=3 or len(x['content_hash'])!=64 for x in result.values())):
        raise ValueError('exact eight successor skill publication proof required')
    return result


def run(connect,*,validate_target,publication,state):
    validate_target(connect)
    proof=skill_proof(publication);registry=AipSkillRegistry(connect);items=[]
    for group in (LOGICS[:3],LOGICS[3:]):
        _,readiness,prepared=prepare_material(connect,validate_target=validate_target,logic_ids=group,skill_revision=3)
        items.extend(prepared)
    if len(items)!=8 or {x[0] for x in items}!=set(proof):raise ValueError('exact eight capability mappings required')
    predecessors={};roles={skill:role for role,skills in ROLE_SKILLS.items() for skill in skills}
    for skill_id,request,deps,preview in items:
        skill=registry.get_skill(skill_id,3)
        if skill.content_hash!=proof[skill_id]['content_hash']:raise ValueError('publication hash changed')
        if preview.readiness.value!='available' or preview.reasons:raise ValueError('current dependencies blocked')
        latest_health(connect,deps.provider_ref)
        logic=skill_id.rsplit('.',1)[1]
        old=registry.get_binding(SCOPE,'a0v-firstchain-skill-'+logic.lower())
        if old.status!='active' or old.skill.asset_id!=skill_id or old.skill.revision!=2 or old.instance_id!=roles[logic]:
            raise ValueError('exact active predecessor binding required')
        predecessors[skill_id]=old
    capabilities=AipCapabilityBindingService(connect,readiness_service=readiness);results=[]
    for skill_id,request,deps,preview in items:
        validate_target(connect);logic=skill_id.rsplit('.',1)[1].lower();key='successor-'+logic
        health=latest_health(connect,deps.provider_ref)
        binding,_=step(state,key+'-cap-create',request,lambda:capabilities.create(SCOPE,request,
            idempotency_key=key+'-cap-create',actor=ACTOR,occurred_at=datetime.now(UTC)))
        command=EvaluateOperationalBindingRequest(expected_version=binding.version,dependencies=deps,
            expected_dependency_snapshot_hash=preview.dependency_snapshot_hash)
        binding,ready,_=step(state,key+'-cap-evaluate',command,lambda:capabilities.evaluate(SCOPE,binding.binding_id,command,
            idempotency_key=key+'-cap-evaluate',actor=ACTOR,evaluated_at=datetime.now(UTC)))
        if ready.readiness.value!='available':raise ValueError('capability readiness changed')
        command=UpdateCapabilityBindingRequest(expected_version=binding.version,from_status='provisioning',to_status='active',
            health='healthy',observed_at=health.observed_at)
        binding,_=step(state,key+'-cap-activate',command,lambda:capabilities.update(SCOPE,binding.binding_id,command,
            idempotency_key=key+'-cap-activate',actor=ACTOR))
        skill=registry.get_skill(skill_id,3);old=predecessors[skill_id]
        command=CreateSkillBindingRequest(binding_id='a0v-model-successor-r3-skill-'+logic,instance_id=old.instance_id,
            skill=exact('SkillTemplate',skill_id,3,skill.content_hash),capability_binding_ids=[binding.binding_id],budget_policy_ref=deps.budget_policy_ref)
        new,_=step(state,key+'-skill-create',command,lambda:registry.create_binding(SCOPE,command,
            idempotency_key=key+'-skill-create',actor=ACTOR,occurred_at=datetime.now(UTC)))
        skill_deps=OperationalBindingDependencies(model_route_ref=skill.model_route_ref,runtime_policy_ref=skill.runtime_policy_ref,
            eval_gate_ref=skill.release_gate_ref,budget_policy_ref=deps.budget_policy_ref)
        command=EvaluateOperationalBindingRequest(expected_version=new.version,dependencies=skill_deps)
        new,ready,_=step(state,key+'-skill-evaluate',command,lambda:registry.evaluate_binding(SCOPE,new.binding_id,command,
            idempotency_key=key+'-skill-evaluate',actor=ACTOR,evaluated_at=datetime.now(UTC)))
        if ready.readiness.value!='available':raise ValueError('skill readiness changed')
        command=UpdateSkillBindingRequest(expected_version=old.version,from_status='active',to_status='suspended')
        step(state,key+'-old-suspend',command,lambda:registry.update_binding(SCOPE,old.binding_id,command,
            idempotency_key=key+'-old-suspend',actor=ACTOR,occurred_at=datetime.now(UTC)))
        command=UpdateSkillBindingRequest(expected_version=new.version,from_status='provisioning',to_status='active')
        new,_=step(state,key+'-skill-activate',command,lambda:registry.update_binding(SCOPE,new.binding_id,command,
            idempotency_key=key+'-skill-activate',actor=ACTOR,occurred_at=datetime.now(UTC)))
        results.append(dict(skillId=skill_id,bindingId=new.binding_id,status=new.status,version=new.version))
    return dict(bindings=results,providerCalls=0,businessRuns=0)
