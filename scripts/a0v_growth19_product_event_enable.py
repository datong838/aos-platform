"""Separate exact approvals for optional event dispatch and internal event enabling."""
import argparse
import json
import a0v_growth19_successor_business as f
from a0v_growth19_product_event_policy_renewal import load_profile as policy_profile

STATE=f.STATE/'event-enable'
PREFIX='a0v-qyh-f-event-enable-20260916-v1'
ACTION=dict(id='ecommerce_growth_event_dispatch',name='配置电商商品事件受控入口',objectType='Case',parameters=[],requiredMarkings=[],submissionCriteria=[])


def load(phase):
    path=STATE/(phase+'-result.json')
    if path.stat().st_mode & 0o777!=0o600:raise ValueError('private enable result required')
    return json.loads(path.read_text())


def run(phase,plane):
    from a0v_qyh_current_product_event_first_chain import freeze,_approve,api,_web_connection
    from aos_api.tenant_scope import TenantScope
    scope=TenantScope('org-org','dev-project');policy=policy_profile()
    intent=STATE/(phase+'-intent.json')
    if intent.exists():raise ValueError('existing enable intent requires read-only inspection')
    if phase=='action':
        with _web_connection(scope) as conn:
            row=conn.execute('SELECT id,name,object_type,parameters,required_markings,submission_criteria FROM meta_action_type WHERE id=%s',(ACTION['id'],)).fetchone()
        expected=None if row is None else dict(id=row['id'],name=row['name'],objectType=row['object_type'],parameters=row['parameters'],requiredMarkings=row['required_markings'],submissionCriteria=row['submission_criteria'])
        if expected is not None and expected!=ACTION:raise ValueError('current event dispatch action differs')
        freeze(intent,ACTION)
        if expected is None:_,expected=api('POST','/v1/actions/types',ACTION)
        result=dict(action=expected)
    elif phase=='approve-dispatch':
        request=dict(schemaVersion='aos.ecommerce.event-control-dispatch/v1',phase='expand',
            installationRef=dict(installationId=f.F_ID,revision=5,lockHash=f.LOCK,overlayRevision='a0v-canonical-ecommerce-v1'),
            generation=f.F_GENERATION,executionEpoch=3,runtimeRevision=6,cutoverGroupId=f.GROUP,expectedGroupRevision=5,
            caseId=policy.CASE,schedulePolicyId=policy.POLICY,idempotencyKey=PREFIX+'-expand')
        payload=dict(caseId=policy.CASE,schedulePolicyId=policy.POLICY,dispatchIntent=request)
        freeze(intent,payload)
        proposal,ref=_approve(ACTION['id'],payload,PREFIX+'-dispatch-approval')
        result=dict(proposalId=proposal.proposal.id,approvalRef=ref,request=request)
    elif phase=='expand':
        from aos_api.ecommerce_event_control_dispatch_lifecycle import EventControlDispatchRequest
        approved=load('approve-dispatch')
        request=EventControlDispatchRequest.model_validate({**approved['request'],'approvalRef':approved['approvalRef']})
        freeze(intent,request.wire())
        result=plane.pipeline_control_factory.build_event_dispatch_lifecycle(scope).transition(scope=scope,request=request,actor=f.ACTOR)
    elif phase=='approve-control':
        policy_ref=policy.load('put')['receiptRef']
        control=dict(schemaVersion='aos.ecommerce.product-event-control-command/v1',idempotencyKey=PREFIX+'-control',policyRef=policy_ref,expectedBindingRevision=0,intent='enable')
        payload=dict(caseId=policy.CASE,schedulePolicyId=policy.POLICY,controlIntent=control)
        freeze(intent,payload)
        proposal,ref=_approve('ecommerce_growth_event_control',payload,PREFIX+'-control-approval')
        result=dict(proposalId=proposal.proposal.id,approvalRef=ref,control=control)
    elif phase=='enable':
        from aos_api.auth import Principal
        from aos_api.ecommerce_growth_canonical_router import EcommerceGrowthCanonicalRouter,ExpectedRuntimeTarget
        from aos_api.ecommerce_growth_host_composition import build_scoped_ecommerce_growth_registry
        approved=load('approve-control');command={**approved['control'],'approvalRef':approved['approvalRef']}
        freeze(intent,command)
        principal=Principal(subject=f.ACTOR,org_id=scope.org_id,project_id=scope.project_id,roles=['admin'])
        router=EcommerceGrowthCanonicalRouter(build_scoped_ecommerce_growth_registry(principal,plane.pipeline_control_factory))
        result=router.dispatch(scope=scope,operation_id='ecommerce_growth_event_control',command=command,expected_runtime=ExpectedRuntimeTarget(f.F_ID,f.F_GENERATION,3))
    else:raise ValueError('unknown enable phase')
    result=dict(result,outcome='CURRENT_F_EVENT_'+phase.upper())
    freeze(STATE/(phase+'-result.json'),result)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['action','approve-dispatch','expand','approve-control','enable']);args=parser.parse_args()
    print(json.dumps(run(args.phase,f.setup()),ensure_ascii=False,indent=2,default=str))


if __name__=='__main__':main()
