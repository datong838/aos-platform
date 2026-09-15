"""Exact F event disable/fence/shrink preceding the event-complete successor."""
import argparse
import json
import a0v_growth19_successor_business as f
from a0v_growth19_product_event_policy_window3 import load_profile as policy_profile
from a0v_qyh_current_product_event_first_chain import freeze,_approve

STATE=f.ROOT.parent/'.aos-recovery-20260916/state/event-complete-package/retire-f'
PREFIX='a0v-event-complete-retire-f-20260916'


def load(phase):
    p=STATE/(phase+'-result.json')
    if not p.is_file() or p.stat().st_mode & 0o777!=0o600:raise ValueError('private preceding retirement result required')
    return json.loads(p.read_text())


def current_dispatch(phase):
    from a0v_formal_text_model_renewal import database_connect
    with database_connect('aos_meta_head')() as c:
        r=c.execute("SELECT * FROM extension_runtime_binding WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s AND generation=%s",(f.F_ID,f.F_GENERATION)).fetchone()
        d=c.execute("SELECT * FROM extension_operation_dispatch_binding WHERE org_id='org-org' AND project_id='dev-project' AND operation_id='ecommerce_growth_event_control'").fetchone()
        enabled=c.execute("SELECT count(*) n FROM automation_schedule_binding WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s AND generation=%s AND enabled",(f.F_ID,f.F_GENERATION)).fetchone()['n']
        source=c.execute("SELECT enabled FROM meta_schedule WHERE org_id='org-org' AND project_id='dev-project' AND id='sch-p02-qyh-controlled-20260913-v1'").fetchone()
    if (r is None or d is None or r['revision']!=6 or r['execution_epoch']!=3 or r['enabled'] is not True
        or r['operation_fence'] is not False or enabled!=0 or source is None or source['enabled'] is not False
        or str(d['installation_id'])!=f.F_ID or str(d['generation'])!=f.F_GENERATION
        or d['operation_fence'] is not (phase=='shrink') or str(d['cutover_group_id'])!=f.GROUP
        or d['cutover_group_revision']!=(6 if phase=='fence' else 7)):
        raise ValueError('exact drained F dispatch state required')
    return dict(schemaVersion='aos.ecommerce.event-control-dispatch/v1',phase=phase,
        installationRef=dict(installationId=f.F_ID,revision=5,lockHash=f.LOCK,overlayRevision='a0v-canonical-ecommerce-v1'),
        generation=f.F_GENERATION,executionEpoch=3,runtimeRevision=6,cutoverGroupId=f.GROUP,
        expectedGroupRevision=d['cutover_group_revision'],caseId=policy_profile().CASE,
        schedulePolicyId=policy_profile().POLICY,idempotencyKey=PREFIX+'-'+phase)


def run(phase):
    intent=STATE/(phase+'-intent.json')
    if intent.exists():raise ValueError('existing retirement intent requires read-only inspection')
    plane=f.setup();policy=policy_profile()
    if phase=='approve-disable':
        control=dict(schemaVersion='aos.ecommerce.product-event-control-command/v1',idempotencyKey=PREFIX+'-disable',
            policyRef=policy.load('put')['receiptRef'],expectedBindingRevision=1,intent='disable')
        payload=dict(caseId=policy.CASE,schedulePolicyId=policy.POLICY,controlIntent=control)
        freeze(intent,payload);bundle,ref=_approve('ecommerce_growth_event_control',payload,PREFIX+'-disable-approval')
        result=dict(approvalRef=ref,control=control,proposalId=bundle.proposal.id)
    elif phase=='disable':
        from aos_api.auth import Principal
        from aos_api.tenant_scope import TenantScope
        from aos_api.ecommerce_growth_canonical_router import EcommerceGrowthCanonicalRouter,ExpectedRuntimeTarget
        from aos_api.ecommerce_growth_host_composition import build_scoped_ecommerce_growth_registry
        approved=load('approve-disable');command={**approved['control'],'approvalRef':approved['approvalRef']}
        freeze(intent,command);scope=TenantScope('org-org','dev-project')
        p=Principal(subject=f.ACTOR,org_id=scope.org_id,project_id=scope.project_id,roles=['admin'])
        router=EcommerceGrowthCanonicalRouter(build_scoped_ecommerce_growth_registry(p,plane.pipeline_control_factory))
        result=router.dispatch(scope=scope,operation_id='ecommerce_growth_event_control',command=command,expected_runtime=ExpectedRuntimeTarget(f.F_ID,f.F_GENERATION,3))
    elif phase in ('approve-fence','approve-shrink'):
        target=phase.removeprefix('approve-');load('disable' if target=='fence' else 'fence')
        request=current_dispatch(target);payload=dict(caseId=policy.CASE,schedulePolicyId=policy.POLICY,dispatchIntent=request)
        freeze(intent,payload);bundle,ref=_approve('ecommerce_growth_event_dispatch',payload,PREFIX+'-'+target+'-approval')
        result=dict(request=request,approvalRef=ref,proposalId=bundle.proposal.id)
    elif phase in ('fence','shrink'):
        from aos_api.ecommerce_event_control_dispatch_lifecycle import EventControlDispatchRequest
        from aos_api.tenant_scope import TenantScope
        approved=load('approve-'+phase)
        if current_dispatch(phase)!=approved['request']:raise ValueError('retirement dispatch approval drifted')
        request=EventControlDispatchRequest.model_validate({**approved['request'],'approvalRef':approved['approvalRef']})
        freeze(intent,request.wire());scope=TenantScope('org-org','dev-project')
        result=plane.pipeline_control_factory.build_event_dispatch_lifecycle(scope).transition(scope=scope,request=request,actor=f.ACTOR)
    else:raise ValueError('unknown retirement phase')
    freeze(STATE/(phase+'-result.json'),dict(result));return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['approve-disable','disable','approve-fence','fence','approve-shrink','shrink']);args=parser.parse_args()
    print(json.dumps(run(args.phase),ensure_ascii=False,default=str))
