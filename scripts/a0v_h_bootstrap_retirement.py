"""Exact H event fence/shrink after its actual Policy5 disable receipt."""
import argparse
import json
import a0v_diagnostic_successor_business as f
from a0v_h_product_window import policy_profile
from a0v_qyh_current_product_event_first_chain import freeze,_approve

STATE=f.STATE/'bootstrap-retirement'
PREFIX='a0v-h-bootstrap-retire-20260916'


def load(phase):
    p=(f.STATE/'analysis-pause/disable-result.json') if phase=='disable' else STATE/(phase+'-result.json')
    if not p.is_file() or p.stat().st_mode & 0o777!=0o600:raise ValueError('private preceding retirement result required')
    return json.loads(p.read_text())


def current_dispatch(phase):
    from a0v_formal_text_model_renewal import database_connect
    with database_connect('aos_meta_head')() as c:
        r=c.execute("SELECT * FROM extension_runtime_binding WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s AND generation=%s",(f.G_ID,f.G_GENERATION)).fetchone()
        d=c.execute("SELECT * FROM extension_operation_dispatch_binding WHERE org_id='org-org' AND project_id='dev-project' AND operation_id='ecommerce_growth_event_control'").fetchone()
        enabled=c.execute("SELECT count(*) n FROM automation_schedule_binding WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s AND generation=%s AND enabled",(f.G_ID,f.G_GENERATION)).fetchone()['n']
        source=c.execute("SELECT enabled FROM meta_schedule WHERE org_id='org-org' AND project_id='dev-project' AND id='sch-p02-qyh-controlled-20260913-v1'").fetchone()
    if (r is None or d is None or r['revision']!=6 or r['execution_epoch']!=3 or r['enabled'] is not True
        or r['operation_fence'] is not False or enabled!=0 or source is None or source['enabled'] is not False
        or str(d['installation_id'])!=f.G_ID or str(d['generation'])!=f.G_GENERATION
        or d['operation_fence'] is not (phase=='shrink') or str(d['cutover_group_id'])!=f.GROUP
        or d['cutover_group_revision']!=(18 if phase=='fence' else 19)):
        raise ValueError('exact drained G dispatch state required')
    return dict(schemaVersion='aos.ecommerce.event-control-dispatch/v1',phase=phase,
        installationRef=dict(installationId=f.G_ID,revision=5,lockHash=f.LOCK,overlayRevision='a0v-canonical-ecommerce-v1'),
        generation=f.G_GENERATION,executionEpoch=3,runtimeRevision=6,cutoverGroupId=f.GROUP,
        expectedGroupRevision=d['cutover_group_revision'],caseId=policy_profile().CASE,
        schedulePolicyId=policy_profile().POLICY,idempotencyKey=PREFIX+'-'+phase)


def run(phase):
    if phase not in ('approve-fence','fence','approve-shrink','shrink'):
        raise ValueError('only exact H event retirement phases allowed')
    intent=STATE/(phase+'-intent.json')
    if intent.exists():raise ValueError('existing retirement intent requires read-only inspection')
    plane=f.setup();policy=policy_profile()
    if phase in ('approve-fence','approve-shrink'):
        target=phase.removeprefix('approve-');load('disable' if target=='fence' else 'fence')
        request=current_dispatch(target);payload=dict(caseId=policy.CASE,schedulePolicyId=policy.POLICY,dispatchIntent=request)
        freeze(intent,payload);bundle,ref=_approve('ecommerce_growth_event_dispatch',payload,PREFIX+'-'+target+'-approval')
        result=dict(request=request,approvalRef=ref,proposalId=bundle.proposal.id)
    elif phase in ('fence','shrink'):
        from aos_api.ecommerce_event_control_dispatch_lifecycle import EventControlDispatchRequest
        from aos_api.tenant_scope import TenantScope
        target=phase
        approved=load('approve-'+target)
        if current_dispatch(target)!=approved['request']:raise ValueError('retirement dispatch approval drifted')
        request=EventControlDispatchRequest.model_validate({**approved['request'],'approvalRef':approved['approvalRef']})
        freeze(intent,request.wire());scope=TenantScope('org-org','dev-project')
        result=plane.pipeline_control_factory.build_event_dispatch_lifecycle(scope).transition(scope=scope,request=request,actor=f.ACTOR)
    else:raise ValueError('unknown retirement phase')
    freeze(STATE/(phase+'-result.json'),dict(result));return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['approve-fence','fence','approve-shrink','shrink']);args=parser.parse_args()
    print(json.dumps(run(args.phase),ensure_ascii=False,default=str))
