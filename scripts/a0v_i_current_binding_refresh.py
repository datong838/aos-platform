"""Refresh only the installed r3 bindings using current real health and Owner CAS."""
import argparse
import json
from datetime import UTC,datetime
import a0v_bootstrap_successor_business as h
from a0v_g_model_successor_apply import require_main
from a0v_firstchain_binding_successor import ACTOR,LOGICS,step
from a0v_firstchain_capability_bindings import prepare_material,SCOPE
from a0v_firstchain_capability_activate import latest_health
from a0v_formal_text_model_renewal import database_connect
from a0v_qyh_current_product_event_first_chain import freeze
from aos_api.aip_capability_binding_service import AipCapabilityBindingService
from aos_api.aip_skill_registry import AipSkillRegistry
from aos_api.aip_agent_registry_contracts import EvaluateOperationalBindingRequest,UpdateCapabilityBindingRequest
from aos_api.aip_production_contract_store import AipProductionContractStore

STATE=h.STATE/'current-health-refresh'


def require_current(capability,skill,request,deps):
    suffix=request.binding_id.removeprefix('a0v-model-successor-r3-').split('-')[0]
    if (not request.binding_id.startswith('a0v-model-successor-r3-') or suffix.upper() not in LOGICS
        or capability.binding_id!=request.binding_id or capability.capability!=request.binding.capability
        or capability.dependencies!=deps or capability.status!='active'
        or skill.binding_id!='a0v-model-successor-r3-skill-'+suffix or skill.skill.revision!=3
        or skill.status!='active' or skill.capability_binding_ids!=[capability.binding_id]):
        raise ValueError('exact active r3 capability and skill required')


def run():
    if (STATE/'intent.json').exists():raise ValueError('existing refresh intent requires receipt inspection')
    h.setup();connect=database_connect('aos_meta_head');require_main(connect)
    with connect() as c:
        binding=c.execute("SELECT enabled,generation,execution_epoch FROM extension_runtime_binding WHERE org_id=%s AND project_id=%s AND installation_id=%s",(*SCOPE.key,h.G_ID)).fetchone()
        if not binding or not binding['enabled'] or str(binding['generation'])!=h.G_GENERATION or binding['execution_epoch']!=3:
            raise ValueError('current I runtime required')
        if c.execute('SELECT 1 FROM automation_schedule_binding WHERE org_id=%s AND project_id=%s AND enabled',SCOPE.key).fetchone():
            raise ValueError('event source must remain paused during refresh')
    registry=AipSkillRegistry(connect);items=[]
    for group in (LOGICS[:3],LOGICS[3:]):
        _,readiness,prepared=prepare_material(connect,validate_target=require_main,logic_ids=group,skill_revision=3)
        items.extend(prepared)
    caps=AipCapabilityBindingService(connect,readiness_service=readiness)
    prepared=[]
    for skill_id,request,deps,preview in items:
        cap=caps.get(SCOPE,request.binding_id);logic=skill_id.rsplit('.',1)[1].lower()
        skill=registry.get_binding(SCOPE,'a0v-model-successor-r3-skill-'+logic)
        require_current(cap,skill,request,deps)
        if preview.readiness.value!='available' or preview.reasons:raise ValueError('current dependency preview blocked')
        health=latest_health(connect,deps.provider_ref)
        prepared.append((logic,cap,skill,deps,preview,health))
    if len(prepared)!=8 or len({x[0] for x in prepared})!=8:raise ValueError('eight exact bindings required')
    freeze(STATE/'intent.json',dict(bindings=[dict(logic=x[0],capability=x[1].binding_id,skill=x[2].binding_id,health=x[5].observation_id) for x in prepared]))
    for logic,cap,skill,deps,preview,health in prepared:
        def execute(name,request,callback):return step(STATE,logic+'-'+name,request,callback)
        command=UpdateCapabilityBindingRequest(expected_version=cap.version,from_status='active',to_status='suspended',health=health.status,observed_at=health.observed_at)
        cap,_=execute('suspend',command,lambda:caps.update(SCOPE,cap.binding_id,command,idempotency_key='a0v-i-refresh-'+logic+'-suspend',actor=ACTOR))
        command=EvaluateOperationalBindingRequest(expected_version=cap.version,dependencies=deps,expected_dependency_snapshot_hash=preview.dependency_snapshot_hash)
        cap,ready,_=execute('evaluate',command,lambda:caps.evaluate(SCOPE,cap.binding_id,command,idempotency_key='a0v-i-refresh-'+logic+'-evaluate',actor=ACTOR,evaluated_at=datetime.now(UTC)))
        if ready.readiness.value!='available':raise ValueError('capability readiness changed')
        command=UpdateCapabilityBindingRequest(expected_version=cap.version,from_status='suspended',to_status='active',health='healthy',observed_at=health.observed_at)
        cap,_=execute('activate',command,lambda:caps.update(SCOPE,cap.binding_id,command,idempotency_key='a0v-i-refresh-'+logic+'-activate',actor=ACTOR))
        command=EvaluateOperationalBindingRequest(expected_version=skill.version,dependencies=skill.dependencies)
        skill,ready,_=execute('skill-evaluate',command,lambda:registry.evaluate_binding(SCOPE,skill.binding_id,command,idempotency_key='a0v-i-refresh-'+logic+'-skill',actor=ACTOR,evaluated_at=datetime.now(UTC)))
        if ready.readiness.value!='available':raise ValueError('skill readiness changed')
    plan=AipProductionContractStore(connect).get_responsibility_plan(SCOPE,'responsibility-plan-63c82d2a75614e1b95f1',2)
    if plan.readiness.value!='ready' or plan.coverage.value!='complete' or plan.blockers:raise ValueError('responsibility plan remains blocked')
    result=plan.model_dump(mode='json',by_alias=True);freeze(STATE/'result.json',result)
    return dict(outcome='I_CURRENT_R3_BINDINGS_REFRESHED',capabilities=8,skills=8,providerCalls=0)


if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False))
