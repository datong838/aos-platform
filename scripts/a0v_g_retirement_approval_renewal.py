"""New exact shrink approval after verified expiry of the preceding event."""
import argparse
import json
import a0v_g_diagnostic_retirement as old
import a0v_g_shrink_after_closure as recovery
import a0v_event_complete_successor_business as g
from a0v_g_unaccepted_analysis_close import read_existing,STATE as CLOSED
from a0v_qyh_current_product_event_first_chain import freeze,_approve
from a0v_formal_text_model_renewal import database_connect

STATE=old.STATE/'approval-renewal'
KEY='a0v-g-retirement-after-closure-20260916'


def current():
    request=old.current_dispatch('shrink');prior=old.load('approve-shrink')
    plan=json.loads((CLOSED/'plan.json').read_text())
    receipts=[read_existing(r) for r in plan['requests']]
    if len({r['receiptId'] for r in receipts})!=21:raise ValueError('unique closure receipts required')
    with database_connect('aos_meta_head')() as c:
        n=c.execute("SELECT count(*) n FROM extension_event_control_dispatch_receipt WHERE org_id='org-org' AND project_id='dev-project' AND idempotency_key=%s",(prior['request']['idempotencyKey'],)).fetchone()['n']
        unresolved=c.execute("""SELECT count(*) n FROM automation_occurrence o LEFT JOIN automation_occurrence_dispatch_attempt a
            USING(org_id,project_id,occurrence_id) WHERE o.org_id='org-org' AND o.project_id='dev-project'
            AND o.installation_id=%s AND o.generation=%s AND (o.status='claimed' OR a.status IN ('claimed','unknown'))""",
            (g.G_ID,g.G_GENERATION)).fetchone()['n']
        expired=c.execute("""SELECT expires_at<clock_timestamp() AS expired FROM aip_action_approval_event
            WHERE org_id='org-org' AND project_id='dev-project' AND approval_event_id=%s""",
            (prior['approvalRef']['resourceId'],)).fetchone()
    recovery.require_counts(receipts=len(receipts),unresolved=unresolved,existing=n)
    if expired is None or expired['expired'] is not True:raise ValueError('verified old approval expiry required')
    request['idempotencyKey']=KEY+'-shrink'
    return request


def run(phase):
    if phase not in ('approve','shrink'):raise ValueError('exact renewal phase required')
    intent=STATE/(phase+'-intent.json')
    if intent.exists():raise ValueError('existing renewal intent requires readback')
    plane=g.setup();request=current()
    if phase=='approve':
        payload=dict(caseId=request['caseId'],schedulePolicyId=request['schedulePolicyId'],dispatchIntent=request)
        freeze(intent,payload)
        bundle,ref=_approve('ecommerce_growth_event_dispatch',payload,KEY+'-approval')
        result=dict(request=request,approvalRef=ref,proposalId=bundle.proposal.id)
    else:
        from aos_api.ecommerce_event_control_dispatch_lifecycle import EventControlDispatchRequest
        from aos_api.tenant_scope import TenantScope
        approved=json.loads((STATE/'approve-result.json').read_text())
        if approved['request']!=request:raise ValueError('renewed request drift')
        body=EventControlDispatchRequest.model_validate({**request,'approvalRef':approved['approvalRef']})
        freeze(intent,body.wire());scope=TenantScope('org-org','dev-project')
        result=plane.pipeline_control_factory.build_event_dispatch_lifecycle(scope).transition(scope=scope,request=body,actor=g.ACTOR)
    freeze(STATE/(phase+'-result.json'),result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['approve','shrink']);a=p.parse_args()
    print(json.dumps(run(a.phase),ensure_ascii=False,default=str))
