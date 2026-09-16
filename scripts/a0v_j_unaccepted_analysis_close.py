"""Close J's 12 refresh-source initializations that have no business acceptance."""
import argparse
import json

import a0v_transaction_successor_business as j
from a0v_formal_text_model_renewal import database_connect
from a0v_j_event_control_refresh_retirement import STATE as RETIRE_STATE, current
from a0v_qyh_current_product_event_first_chain import freeze


STATE = j.STATE / 'unaccepted-analysis-refresh-closure'
PREFIX = 'a0v-j-refresh-unaccepted-analysis-20260916'


def fence_receipt():
    path = RETIRE_STATE / 'fence-result.json'
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError('private J refresh fence result required')
    result = json.loads(path.read_text())
    receipt = result.get('receipt')
    if (not isinstance(receipt, dict) or receipt.get('phase') != 'fence'
        or receipt.get('receiptId') != result.get('replayReceiptId')
        or result.get('sameKeyReplay') is not True):
        raise ValueError('exact replayed J refresh fence receipt required')
    return receipt


def prepare():
    j.setup()
    current('shrink')
    fence = fence_receipt()
    with database_connect('aos_meta_head')() as conn:
        conn.execute("SELECT set_config('aos.org_id','org-org',true),"
                     "set_config('aos.project_id','dev-project',true)")
        rows = conn.execute("""SELECT o.occurrence_id,a.target_idempotency_key,o.policy_revision,
              (SELECT count(*) FROM ecommerce_growth_runtime_command_receipt r
                WHERE r.org_id=o.org_id AND r.project_id=o.project_id
                  AND r.operation_id='ecommerce_growth_analysis_advance'
                  AND r.idempotency_key=a.target_idempotency_key) AS receipt_count,
              (SELECT count(*) FROM ecommerce_investigation_run x
                WHERE x.org_id=o.org_id AND x.project_id=o.project_id
                  AND (x.trigger_key=a.target_idempotency_key OR x.run_id='analysis-'||substr(encode(
                    sha256(convert_to(o.org_id||chr(31)||o.project_id||chr(31)||a.target_idempotency_key,'UTF8')),
                    'hex'),1,32))) AS run_count
            FROM automation_occurrence o
            JOIN automation_occurrence_dispatch_attempt a USING(org_id,project_id,occurrence_id)
            WHERE o.org_id='org-org' AND o.project_id='dev-project'
              AND o.installation_id=%s AND o.generation=%s AND o.execution_epoch=3
              AND o.trigger_source='event' AND o.operation_id='ecommerce_growth_analysis_advance'
              AND o.status='needs_attention' AND a.status='unknown'
              AND a.claim_until<clock_timestamp() ORDER BY o.occurrence_id""",
            (j.G_ID, j.G_GENERATION)).fetchall()
    if (len(rows) != 12 or {row['policy_revision'] for row in rows} != {7}
        or any(row['receipt_count'] != 0 or row['run_count'] != 0 for row in rows)):
        raise ValueError('exact 12 unaccepted J refresh-source initializations required')
    requests = [dict(schemaVersion='aos.ecommerce.unaccepted-analysis-closure/v1',
        occurrenceId=str(row['occurrence_id']), fenceReceiptId=fence['receiptId'],
        fenceContentHash=fence['contentHash'], idempotencyKey=f'{PREFIX}-{row["occurrence_id"]}')
        for row in rows]
    plan = dict(installationId=j.G_ID, generation=j.G_GENERATION, actor=j.ACTOR,
                requests=requests, count=12, businessAccepted=False, externalEffects=False,
                targetReceiptCount=0, investigationRunCount=0)
    freeze(STATE / 'plan.json', plan)
    return dict(outcome='J_REFRESH_UNACCEPTED_CLOSURE_PLAN_RECORDED', count=12)


def read_existing(request):
    from aos_api.asset_registry.canonical_json import canonical_sha256
    with database_connect('aos_meta_head')() as conn:
        row = conn.execute("""SELECT authority_data,content_hash,request_hash,actor
            FROM ecommerce_unaccepted_analysis_closure_receipt
            WHERE org_id='org-org' AND project_id='dev-project' AND idempotency_key=%s""",
            (request['idempotencyKey'],)).fetchone()
    if (row is None or row['actor'] != j.ACTOR
        or row['request_hash'] != canonical_sha256(request)
        or row['content_hash'] != canonical_sha256(row['authority_data'])):
        raise ValueError('prior J closure intent needs inspection; do not resend')
    return {**row['authority_data'], 'contentHash': row['content_hash'], 'replayed': True}


def apply():
    j.setup()
    current('shrink')
    from aos_api.ecommerce_growth_registration_connection import registration_connection
    from aos_api.ecommerce_unaccepted_analysis_closure import (
        UnacceptedAnalysisClosureRequest, UnacceptedAnalysisClosureService,
    )
    from aos_api.tenant_scope import TenantScope
    path = STATE / 'plan.json'
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError('private J closure plan required')
    plan = json.loads(path.read_text())
    if (plan.get('installationId') != j.G_ID or plan.get('generation') != j.G_GENERATION
        or plan.get('actor') != j.ACTOR or plan.get('count') != 12
        or len(plan.get('requests', ())) != 12
        or len({item['occurrenceId'] for item in plan['requests']}) != 12
        or plan.get('businessAccepted') is not False or plan.get('externalEffects') is not False):
        raise ValueError('exact J unaccepted closure plan required')
    service = UnacceptedAnalysisClosureService(connect=registration_connection)
    receipts = []
    scope = TenantScope('org-org', 'dev-project')
    for wire in plan['requests']:
        request = UnacceptedAnalysisClosureRequest.model_validate(wire)
        intent = STATE / f'{request.occurrence_id}-intent.json'
        if intent.exists():
            if json.loads(intent.read_text()) != wire:
                raise ValueError('retained J closure intent drifted')
            receipt = read_existing(wire)
        else:
            freeze(intent, wire)
            receipt = service.close(scope=scope, request=request, actor=j.ACTOR)
        result = STATE / f'{request.occurrence_id}-result.json'
        if not result.exists():
            freeze(result, receipt)
        receipts.append(dict(receiptId=receipt['receiptId'], contentHash=receipt['contentHash'],
                             businessAccepted=receipt['businessAccepted']))
    result = dict(outcome='J_12_REFRESH_INITIALIZATIONS_CLOSED_UNACCEPTED', count=len(receipts),
                  receipts=receipts, businessAccepted=False, externalEffects=0)
    if not (STATE / 'result.json').exists():
        freeze(STATE / 'result.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('prepare', 'apply'))
    args = parser.parse_args()
    print(json.dumps(globals()[args.mode](), ensure_ascii=False))
