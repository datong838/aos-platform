"""Close only H's 9 held event initializations through the formal recovery service."""
import argparse
import json
import a0v_diagnostic_successor_business as g
from a0v_qyh_current_product_event_first_chain import freeze
from a0v_formal_text_model_renewal import database_connect

STATE=g.STATE/'unaccepted-analysis-closure'
PREFIX='a0v-h-unaccepted-analysis-20260916'


def prepare():
    from a0v_h_bootstrap_retirement import current_dispatch,load
    g.setup();current_dispatch('shrink');fence=load('fence')
    with database_connect('aos_meta_head')() as c:
        rows=c.execute('''SELECT o.occurrence_id,a.target_idempotency_key,o.policy_revision
            FROM automation_occurrence o JOIN automation_occurrence_dispatch_attempt a USING(org_id,project_id,occurrence_id)
            WHERE o.org_id='org-org' AND o.project_id='dev-project' AND o.installation_id=%s AND o.generation=%s
            AND o.execution_epoch=3 AND o.trigger_source='event' AND o.operation_id='ecommerce_growth_analysis_advance'
            AND o.status='needs_attention' AND a.status='unknown' AND a.claim_until<clock_timestamp()
            ORDER BY o.occurrence_id''',(g.G_ID,g.G_GENERATION)).fetchall()
        if len(rows)!=9 or {r['policy_revision'] for r in rows}!={5}:
            raise ValueError('exact 9 H unknown initializations required')
    requests=[dict(schemaVersion='aos.ecommerce.unaccepted-analysis-closure/v1',occurrenceId=str(r['occurrence_id']),
        fenceReceiptId=fence['receiptId'],fenceContentHash=fence['contentHash'],
        idempotencyKey=PREFIX+'-'+str(r['occurrence_id'])) for r in rows]
    plan=dict(installationId=g.G_ID,generation=g.G_GENERATION,actor=g.ACTOR,requests=requests,count=9,
              businessAccepted=False,externalEffects=False)
    freeze(STATE/'plan.json',plan)
    return dict(outcome='H_UNACCEPTED_CLOSURE_PLAN_RECORDED',count=9)


def read_existing(request):
    from aos_api.asset_registry.canonical_json import canonical_sha256
    with database_connect('aos_meta_head')() as c:
        row=c.execute('''SELECT authority_data,content_hash,request_hash,actor
            FROM ecommerce_unaccepted_analysis_closure_receipt WHERE org_id='org-org'
            AND project_id='dev-project' AND idempotency_key=%s''',(request['idempotencyKey'],)).fetchone()
    if (row is None or row['actor']!=g.ACTOR or row['request_hash']!=canonical_sha256(request)
        or row['content_hash']!=canonical_sha256(row['authority_data'])):
        raise ValueError('prior closure intent needs inspection; do not resend')
    return {**row['authority_data'],'contentHash':row['content_hash'],'replayed':True}


def apply():
    g.setup()
    from aos_api.ecommerce_growth_registration_connection import registration_connection
    from aos_api.ecommerce_unaccepted_analysis_closure import UnacceptedAnalysisClosureService,UnacceptedAnalysisClosureRequest
    from aos_api.tenant_scope import TenantScope
    from a0v_h_bootstrap_retirement import current_dispatch
    current_dispatch('shrink')
    plan=json.loads((STATE/'plan.json').read_text())
    if (plan.get('installationId')!=g.G_ID or plan.get('generation')!=g.G_GENERATION or plan.get('actor')!=g.ACTOR
        or plan.get('count')!=9 or len(plan.get('requests',[]))!=9
        or len({r['occurrenceId'] for r in plan['requests']})!=9):
        raise ValueError('exact H closure plan required')
    service=UnacceptedAnalysisClosureService(connect=registration_connection)
    receipts=[]
    for wire in plan['requests']:
        request=UnacceptedAnalysisClosureRequest.model_validate(wire)
        intent=STATE/(request.occurrence_id+'-intent.json')
        if intent.exists():
            if json.loads(intent.read_text())!=wire:raise ValueError('retained closure intent drift')
            receipt=read_existing(wire)
        else:
            freeze(intent,wire)
            receipt=service.close(scope=TenantScope('org-org','dev-project'),request=request,actor=g.ACTOR)
        result=STATE/(request.occurrence_id+'-result.json')
        if not result.exists():freeze(result,receipt)
        receipts.append(dict(receiptId=receipt['receiptId'],contentHash=receipt['contentHash']))
    result=dict(outcome='H_9_UNACCEPTED_INITIALIZATIONS_CLOSED',count=len(receipts),receipts=receipts,businessAccepted=False)
    if not (STATE/'result.json').exists():freeze(STATE/'result.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','apply']);args=parser.parse_args()
    print(json.dumps(globals()[args.mode](),ensure_ascii=False))
