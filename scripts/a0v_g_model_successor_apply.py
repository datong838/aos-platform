"""Fixed G model-dependency successor after isolated clone verification."""
import argparse
import json
from datetime import UTC,datetime
import a0v_event_complete_successor_business as g
import a0v_firstchain_model_successor_rehearsal as rehearsal
from a0v_formal_text_model_renewal import database_connect
from a0v_qyh_current_product_event_first_chain import freeze

STATE=g.STATE/'model-successor'
MODEL_HASH='9a4e4f014294927feb6f955b7e2adb793cf41138c83bb54aef271971b6acc865'
ROUTE_HASH='343cad51caa8e42f120e17bc25ec9a4fd8e7a9f79ed6f182368d8ce7cd244455'
POLICY_HASH='ede2de2dffa1cf0f3e012c54f5cc943b7470d90aa7b4a7575ea75d9dcd4ffbab'
LOGICS=('D01','D02','D03','S01','P01','C06','A02','G06')
ACTOR='a0v-g-model-successor-owner'


def load(path):
    if path.is_symlink() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError('private exact evidence required')
    return json.loads(path.read_text())


def require_main(connect):
    from aos_api.aip_model_runtime_store import AipModelRuntimeStore
    from aos_api.tenant_scope import TenantScope
    scope=TenantScope('org-org','dev-project')
    with connect() as conn:
        if conn.info.dbname!='aos_meta_head':raise ValueError('exact main database required')
        row=conn.execute("SELECT enabled,installation_id,generation,execution_epoch FROM automation_schedule_binding WHERE org_id=%s AND project_id=%s AND policy_id=%s AND policy_revision=3",
            (*scope.key,'product-event-qyh-full-store-generation-f-20260916')).fetchone()
        if not row or row['enabled'] or str(row['installation_id'])!=g.G_ID or str(row['generation'])!=g.G_GENERATION or row['execution_epoch']!=3:
            raise ValueError('exact G event pause required')
    runtime=AipModelRuntimeStore(connect)
    model=runtime.get_model(scope,'a0v-agnes-2-5-flash-readonly-dev')
    route=runtime.get_route(scope,'a0v-ecommerce-text-readonly-v1')
    policy=runtime.get_policy(scope,'a0v-ecommerce-runtime-policy-v1')
    if (model.revision,model.content_hash,route.revision,route.content_hash,policy.revision,policy.content_hash)!=(4,MODEL_HASH,4,ROUTE_HASH,5,POLICY_HASH):
        raise ValueError('exact current model authority drifted')
    return scope,model


def run(phase):
    intent=STATE/(phase+'-intent.json')
    if intent.exists():raise ValueError('existing main successor intent requires read-only receipt inspection')
    if phase not in ('graphs','publication','contracts','bindings','verify'):raise ValueError('unsupported phase')
    g.setup()
    proof=load(rehearsal.STATE/'responsibility-readback.json')
    if proof.get('readiness')!='ready' or proof.get('coverage')!='complete' or proof.get('blockers'):
        raise ValueError('successful clone responsibility proof required')
    connect=database_connect('aos_meta_head');scope,model=require_main(connect)
    from a0v_firstchain_skill_publication import materialize_contracts,contract_components,exact_model_alias
    freeze(intent,dict(phase=phase,installationId=g.G_ID,modelHash=MODEL_HASH,routeHash=ROUTE_HASH,policyHash=POLICY_HASH))
    if phase=='graphs':
        from aos_api.aip_logic_graph_store import LogicGraphStore
        from aos_api.aip_skill_registry import AipSkillRegistry
        from a0v_firstchain_model_successor import replacement,apply_graph
        store=LogicGraphStore(connect);skills=AipSkillRegistry(connect);items=[]
        for key in LOGICS:
            ref=skills.get_skill('ecommerce.skill.'+key,2).logic_revision_ref
            current=store.get(*scope.key,ref.asset_id)
            previous=load(rehearsal.STATE/(key.lower()+'-graph-intent.json'))
            if current.revision!=ref.revision or current.graph_hash!=ref.content_hash or previous['previousHash']!=current.graph_hash:
                raise ValueError('main graph differs from rehearsed predecessor')
            aliases={n.config['model'] for n in current.nodes if n.kind=='use_llm'}
            if len(aliases)!=1:raise ValueError('unique exact old model required')
            build,_,_=contract_components(key)
            items.append((key,current,replacement(current,build(aliases.pop()),build(exact_model_alias(model)))))
        results=[]
        for key,current,command in items:
            require_main(connect)
            result=apply_graph(store,scope,ACTOR,current,command,STATE/(key.lower()+'-graph-intent.json'))
            results.append(dict(logic=key,revision=result.revision,hash=result.graph_hash))
        result=dict(graphs=results)
    elif phase=='publication':
        load(STATE/'graphs-result.json')
        result=materialize_contracts(connect,require_target=lambda c:require_main(c),database='aos_meta_head',
            authority_scope='development-model-successor-main',logic_ids=LOGICS)
    elif phase=='contracts':
        load(STATE/'publication-result.json')
        import a0v_firstchain_internal_license as license
        import a0v_firstchain_eval_contracts as contracts
        results=[]
        for group in (LOGICS[:3],LOGICS[3:]):
            for name,module in (('license',license),('contracts',contracts)):
                item=module.materialize(connect,database='aos_meta_head',validate_target=lambda c:require_main(c),apply=True,logic_ids=group,skill_revision=3)
                freeze(STATE/(name+'-'+group[0].lower()+'-result.json'),item)
                results.append(dict(kind=name,group=list(group),result=item))
        result=dict(results=results)
    elif phase=='bindings':
        load(STATE/'contracts-result.json')
        from a0v_firstchain_binding_successor import run as bind
        result=bind(connect,validate_target=lambda c:require_main(c),publication=load(STATE/'publication-result.json'),state=STATE/'bindings')
    else:
        load(STATE/'bindings-result.json')
        from aos_api.aip_production_contract_store import AipProductionContractStore
        plan=AipProductionContractStore(connect).get_responsibility_plan(scope,'responsibility-plan-63c82d2a75614e1b95f1',2)
        result=plan.model_dump(mode='json',by_alias=True)
        if plan.readiness.value!='ready' or plan.coverage.value!='complete' or plan.blockers:raise ValueError('main responsibility remains blocked')
    freeze(STATE/(phase+'-result.json'),result)
    return dict(phase=phase,outcome='G_MODEL_SUCCESSOR_PHASE_VERIFIED')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['graphs','publication','contracts','bindings','verify']);args=parser.parse_args()
    print(json.dumps(run(args.phase)))
