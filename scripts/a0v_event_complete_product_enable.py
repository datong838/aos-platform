"""Separate exact approvals for optional event dispatch and internal event enabling."""
import argparse
import json
import a0v_event_complete_successor_business as f
import a0v_event_complete_product_policy as current_policy

def policy_profile():
    return current_policy

STATE=f.STATE/'event-enable'
PREFIX='a0v-qyh-g-event-enable-20260916-v1'
EXPECTED_GROUP_REVISION=11
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
            installationRef=dict(installationId=f.G_ID,revision=5,lockHash=f.LOCK,overlayRevision='a0v-canonical-ecommerce-v1'),
            generation=f.G_GENERATION,executionEpoch=3,runtimeRevision=6,cutoverGroupId=f.GROUP,expectedGroupRevision=EXPECTED_GROUP_REVISION,
            caseId=policy.CASE,schedulePolicyId=policy.POLICY,idempotencyKey=PREFIX+'-expand')
        payload=dict(caseId=policy.CASE,schedulePolicyId=policy.POLICY,dispatchIntent=request)
        freeze(intent,payload)
        proposal,ref=_approve(ACTION['id'],payload,PREFIX+'-dispatch-approval')
        result=dict(proposalId=proposal.proposal.id,approvalRef=ref,request=request)
    elif phase in ('expand','expand-recovered'):
        from aos_api.ecommerce_event_control_dispatch_lifecycle import EventControlDispatchRequest
        approved=load('approve-dispatch')
        request=EventControlDispatchRequest.model_validate({**approved['request'],'approvalRef':approved['approvalRef']})
        if phase=='expand-recovered':
            from a0v_formal_text_model_renewal import database_connect
            with database_connect('aos_meta_head')() as conn:
                count=conn.execute("SELECT count(*) AS n FROM extension_event_control_dispatch_receipt WHERE org_id='org-org' AND project_id='dev-project' AND idempotency_key=%s",(request.idempotency_key,)).fetchone()['n']
                rows=conn.execute("SELECT operation_id,installation_id,generation,execution_epoch,operation_fence,cutover_group_revision FROM extension_operation_dispatch_binding WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s",(f.GROUP,)).fetchall()
            from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
            if (count!=0 or {r['operation_id'] for r in rows}!=set(ECOMMERCE_GROWTH_OPERATIONS)
                or any(str(r['installation_id'])!=f.G_ID or str(r['generation'])!=f.G_GENERATION or r['execution_epoch']!=3 or r['operation_fence'] is not False or r['cutover_group_revision']!=EXPECTED_GROUP_REVISION for r in rows)
                or json.loads((STATE/'expand-intent.json').read_text())!=request.wire()):
                raise ValueError('failed expansion is not proven absent and unchanged')
            freeze(STATE/'expand-recovered-precheck.json',dict(receiptCount=count,entries=len(rows),groupRevision=EXPECTED_GROUP_REVISION))
        freeze(intent,request.wire())
        result=plane.pipeline_control_factory.build_event_dispatch_lifecycle(scope).transition(scope=scope,request=request,actor=f.ACTOR)
    elif phase=='approve-control':
        policy_ref=policy.load('put')['receiptRef']
        control=dict(schemaVersion='aos.ecommerce.product-event-control-command/v1',idempotencyKey=PREFIX+'-control',policyRef=policy_ref,expectedBindingRevision=0,intent='enable')
        payload=dict(caseId=policy.CASE,schedulePolicyId=policy.POLICY,controlIntent=control)
        freeze(intent,payload)
        proposal,ref=_approve('ecommerce_growth_event_control',payload,PREFIX+'-control-approval')
        result=dict(proposalId=proposal.proposal.id,approvalRef=ref,control=control)
    elif phase in ('enable','enable-recovered'):
        from aos_api.auth import Principal
        from aos_api.ecommerce_growth_canonical_router import EcommerceGrowthCanonicalRouter,ExpectedRuntimeTarget
        from aos_api.ecommerce_growth_host_composition import build_scoped_ecommerce_growth_registry
        approved=load('approve-control');command={**approved['control'],'approvalRef':approved['approvalRef']}
        if phase=='enable-recovered':
            from a0v_formal_text_model_renewal import database_connect
            with database_connect('aos_meta_head')() as conn:
                enabled=conn.execute("SELECT enabled FROM ecommerce_investigation_schedule_policy_head WHERE org_id='org-org' AND project_id='dev-project' AND schedule_policy_id=%s",(policy.POLICY,)).fetchone()
                bindings=conn.execute("SELECT count(*) AS n FROM automation_schedule_binding WHERE org_id='org-org' AND project_id='dev-project' AND policy_id=%s",(policy.POLICY,)).fetchone()['n']
                receipts=conn.execute("SELECT count(*) AS n FROM ecommerce_product_event_control_receipt WHERE org_id='org-org' AND project_id='dev-project' AND idempotency_key=%s",(command['idempotencyKey'],)).fetchone()['n']
            if enabled is None or enabled['enabled'] is not False or bindings!=0 or receipts!=0 or json.loads((STATE/'enable-intent.json').read_text())!=command:
                raise ValueError('failed enable is not proven absent')
            freeze(STATE/'enable-recovered-precheck.json',dict(bindings=bindings,receipts=receipts,enabled=False))
        freeze(intent,command)
        principal=Principal(subject=f.ACTOR,org_id=scope.org_id,project_id=scope.project_id,roles=['admin'])
        router=EcommerceGrowthCanonicalRouter(build_scoped_ecommerce_growth_registry(principal,plane.pipeline_control_factory))
        result=router.dispatch(scope=scope,operation_id='ecommerce_growth_event_control',command=command,expected_runtime=ExpectedRuntimeTarget(f.G_ID,f.G_GENERATION,3))
    else:raise ValueError('unknown enable phase')
    result=dict(result,outcome='CURRENT_G_EVENT_'+phase.upper())
    freeze(STATE/(phase+'-result.json'),result)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['action','approve-dispatch','expand','expand-recovered','approve-control','enable','enable-recovered']);args=parser.parse_args()
    print(json.dumps(run(args.phase,f.setup()),ensure_ascii=False,indent=2,default=str))


if __name__=='__main__':main()
