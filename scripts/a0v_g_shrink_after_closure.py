"""One exact recovery of a known rejected shrink after formal unknown closure."""
import json
import a0v_g_diagnostic_retirement as previous
import a0v_event_complete_successor_business as g
from a0v_g_unaccepted_analysis_close import read_existing,STATE as CLOSURE_STATE
from a0v_qyh_current_product_event_first_chain import freeze
from a0v_formal_text_model_renewal import database_connect

STATE=previous.STATE/'after-closure'


def require_counts(*,receipts,unresolved,existing):
    if (receipts,unresolved,existing)!=(21,0,0):
        raise ValueError('complete closure, drained target and absent shrink receipt required')


def run():
    intent=STATE/'recovery-intent.json'
    if intent.exists():raise ValueError('existing recovery intent requires readback')
    plane=g.setup()
    from aos_api.ecommerce_event_control_dispatch_lifecycle import EventControlDispatchRequest
    from aos_api.tenant_scope import TenantScope
    current=previous.current_dispatch('shrink');approved=previous.load('approve-shrink')
    wire=EventControlDispatchRequest.model_validate({**current,'approvalRef':approved['approvalRef']}).wire()
    old=json.loads((previous.STATE/'shrink-intent.json').read_text())
    if old!=wire or approved['request']!=current or (previous.STATE/'shrink-result.json').exists():
        raise ValueError('exact rejected shrink request required')
    plan=json.loads((CLOSURE_STATE/'plan.json').read_text())
    closures=[read_existing(r) for r in plan['requests']]
    if (len({r['receiptId'] for r in closures})!=21 or any(r['businessAccepted'] is not False for r in closures)
        or any(r['priorOccurrence']['installation_id']!=g.G_ID or r['priorOccurrence']['generation']!=g.G_GENERATION
               for r in closures)):
        raise ValueError('exact G closure receipts required')
    with database_connect('aos_meta_head')() as c:
        existing=c.execute("""SELECT count(*) n FROM extension_event_control_dispatch_receipt
            WHERE org_id='org-org' AND project_id='dev-project' AND idempotency_key=%s""",(wire['idempotencyKey'],)).fetchone()['n']
        unresolved=c.execute("""SELECT count(*) n FROM automation_occurrence o
            LEFT JOIN automation_occurrence_dispatch_attempt a USING(org_id,project_id,occurrence_id)
            WHERE o.org_id='org-org' AND o.project_id='dev-project' AND o.installation_id=%s AND o.generation=%s
            AND (o.status='claimed' OR a.status IN ('claimed','unknown'))""",(g.G_ID,g.G_GENERATION)).fetchone()['n']
    require_counts(receipts=len(closures),unresolved=unresolved,existing=existing)
    freeze(intent,dict(request=wire,closureReceipts=[dict(receiptId=r['receiptId'],contentHash=r['contentHash']) for r in closures],
                       priorTargetReceipts=existing,unresolved=unresolved))
    scope=TenantScope('org-org','dev-project')
    result=plane.pipeline_control_factory.build_event_dispatch_lifecycle(scope).transition(
        scope=scope,request=EventControlDispatchRequest.model_validate(wire),actor=g.ACTOR)
    freeze(STATE/'result.json',result)
    return result


if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False,default=str))
