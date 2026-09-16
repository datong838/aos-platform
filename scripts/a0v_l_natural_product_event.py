"""Arm, observe, and disarm one Cron-only L Product source window."""
import argparse
from datetime import datetime, timezone
import json
import os

import a0v_l_successor_business as current
import a0v_l_product_window as window
from a0v_qyh_current_product_event_first_chain import api, freeze

STATE = current.STATE / 'natural-product-event'
SCHEDULE = 'sch-p02-qyh-controlled-20260913-v1'
POLICY = 'product-event-qyh-full-store-generation-f-20260916'
POLICY_REVISION = 8


def _private(name):
    path = STATE / name
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError('private natural-event evidence required')
    return json.loads(path.read_text())


def snapshot():
    from a0v_formal_text_model_renewal import database_connect
    from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
    with database_connect('aos_meta_head')() as conn:
        schedule = conn.execute('''SELECT id,cron,pipeline_id,enabled,ingest,last_run,updated_at
            FROM meta_schedule WHERE org_id='org-org' AND project_id='dev-project' AND id=%s''',
            (SCHEDULE,)).fetchone()
        policy = conn.execute('''SELECT schedule_policy_id,current_revision,case_id,enabled,
            content_hash,updated_at FROM ecommerce_investigation_schedule_policy_head
            WHERE org_id='org-org' AND project_id='dev-project' AND schedule_policy_id=%s''',
            (POLICY,)).fetchone()
        binding = conn.execute('''SELECT policy_id,policy_revision,policy_hash,operation_id,
            installation_id,generation,execution_epoch,effective_from,effective_until,approved,
            enabled,watermark,revision FROM automation_schedule_binding
            WHERE org_id='org-org' AND project_id='dev-project' AND policy_id=%s
              AND policy_revision=%s''', (POLICY, POLICY_REVISION)).fetchone()
        routes = [dict(row) for row in conn.execute('''SELECT operation_id,handler_kind,
            installation_id,generation,execution_epoch,operation_fence,revision,cutover_group_revision
            FROM extension_operation_dispatch_binding WHERE org_id='org-org' AND project_id='dev-project'
              AND cutover_group_id=%s ORDER BY operation_id''', (current.GROUP,)).fetchall()]
        armed = None
        intent = STATE / 'arm-intent.json'
        if intent.exists():
            armed = json.loads(intent.read_text())['armedAt']
        since = armed or datetime.now(timezone.utc).isoformat()
        runs = [dict(row) for row in conn.execute('''SELECT id,status,trigger,scheduled_for,
            started_at,finished_at,rows_written,error_code,executor_stopped FROM meta_schedule_run
            WHERE org_id='org-org' AND project_id='dev-project' AND schedule_id=%s
              AND started_at >= %s ORDER BY started_at''', (SCHEDULE, since)).fetchall()]
        ingress = [dict(row) for row in conn.execute('''SELECT run_id,pipeline_id,source_id,
            source_revision,envelope_hash,created_at FROM ecommerce_ingress_command
            WHERE org_id='org-org' AND project_id='dev-project' AND created_at >= %s
            ORDER BY created_at''', (since,)).fetchall()]
        occurrences = [dict(row) for row in conn.execute('''SELECT occurrence_id,policy_revision,
            installation_id,generation,execution_epoch,trigger_source,source_event_id,status,
            receipt_ref,created_at,updated_at FROM automation_occurrence
            WHERE org_id='org-org' AND project_id='dev-project' AND policy_id=%s
              AND policy_revision=%s ORDER BY created_at''', (POLICY, POLICY_REVISION)).fetchall()]
        attempts = [dict(row) for row in conn.execute('''SELECT a.attempt_id,a.occurrence_id,
            a.target_idempotency_key,a.status,a.claimed_at,a.claim_until,a.receipt_ref,a.resolved_at
            FROM automation_occurrence_dispatch_attempt a JOIN automation_occurrence o
              USING(org_id,project_id,occurrence_id)
            WHERE a.org_id='org-org' AND a.project_id='dev-project' AND o.policy_id=%s
              AND o.policy_revision=%s ORDER BY a.claimed_at''', (POLICY, POLICY_REVISION)).fetchall()]
        investigations = [dict(row) for row in conn.execute('''SELECT run_id,version,case_id,
            lifecycle,control,analysis_type,trigger_kind,trigger_key,created_at
            FROM ecommerce_investigation_run WHERE org_id='org-org' AND project_id='dev-project'
              AND created_at >= %s ORDER BY created_at''', (since,)).fetchall()]
        inflight = dict(conn.execute('''SELECT
            (SELECT count(*) FROM extension_runtime_execution_attempt WHERE org_id='org-org'
              AND project_id='dev-project' AND installation_id=%s AND generation=%s
              AND state='running') AS running,
            (SELECT count(*) FROM automation_occurrence_dispatch_attempt a JOIN automation_occurrence o
              USING(org_id,project_id,occurrence_id) WHERE a.org_id='org-org'
              AND a.project_id='dev-project' AND o.policy_id=%s AND o.policy_revision=%s
              AND a.status IN ('claimed','unknown')) AS unresolved''',
            (current.L_ID, current.L_GENERATION, POLICY, POLICY_REVISION)).fetchone())
        canary = conn.execute("""SELECT count(*) AS n FROM extension_operation_dispatch_binding
            WHERE org_id='dev-org' AND project_id='dev-project'""").fetchone()['n']
    expected = set(ECOMMERCE_GROWTH_OPERATIONS) | {'ecommerce_growth_event_control'}
    return {'at': datetime.now(timezone.utc).isoformat(), 'schedule': dict(schedule) if schedule else None,
            'policy': dict(policy) if policy else None, 'binding': dict(binding) if binding else None,
            'routes': routes, 'expectedOperations': sorted(expected), 'runs': runs, 'ingress': ingress,
            'occurrences': occurrences, 'attempts': attempts, 'investigationRuns': investigations,
            'inflight': inflight, 'negativeCanaryDispatch': canary}


def validate_ready(value, *, require_drained=True):
    schedule, policy, binding, routes = (value[k] for k in ('schedule','policy','binding','routes'))
    if (schedule is None or schedule['cron'] != '0 * * * *'
        or schedule['pipeline_id'] != 'P02-product-qyh'
        or schedule['ingest'] != {'kind': 'pipeline-live-v1', 'pipelineId': 'P02-product-qyh'}
        or policy is None or policy['current_revision'] != POLICY_REVISION or policy['enabled'] is not False
        or binding is None or binding['policy_revision'] != POLICY_REVISION
        or str(binding['installation_id']) != current.L_ID
        or str(binding['generation']) != current.L_GENERATION or binding['execution_epoch'] != 3
        or binding['approved'] is not True or binding['enabled'] is not True
        or binding['revision'] != 1 or binding['effective_until'] <= datetime.now(timezone.utc)
        or len(routes) != 10 or [row['operation_id'] for row in routes] != value['expectedOperations']
        or any(row['handler_kind'] != 'extension' or str(row['installation_id']) != current.L_ID
               or str(row['generation']) != current.L_GENERATION or row['execution_epoch'] != 3
               or row['operation_fence'] is not False or row['cutover_group_revision'] != 37
               for row in routes)
        or (require_drained and value['inflight'] != {'running': 0, 'unresolved': 0})
        or any(count < 0 for count in value['inflight'].values())
        or value['negativeCanaryDispatch'] != 0):
        raise ValueError('exact L natural Product window required')
    return value


def arm():
    intent = STATE / 'arm-intent.json'
    if intent.exists():
        raise ValueError('existing arm intent requires read-only observation')
    before = validate_ready(snapshot())
    if before['schedule']['enabled'] is not False or before['runs'] or before['ingress']:
        raise ValueError('clean disabled natural window required')
    material = {'scheduleId': SCHEDULE, 'policyId': POLICY, 'policyRevision': POLICY_REVISION,
                'installationId': current.L_ID, 'generation': current.L_GENERATION,
                'executionEpoch': 3, 'cron': '0 * * * *', 'maxSourceCalls': 1,
                'manualRunAllowed': False, 'armedAt': datetime.now(timezone.utc).isoformat()}
    freeze(intent, material)
    status, body = api('PATCH', f'/v1/schedules/{SCHEDULE}', {'enabled': True})
    after = snapshot()
    if status != 200 or after['schedule']['enabled'] is not True:
        raise ValueError('natural schedule enable readback differs')
    result = {'outcome': 'L_NATURAL_PRODUCT_CRON_ARMED', 'status': status, 'body': body,
              'snapshot': after}
    freeze(STATE / 'arm-result.json', result)
    return result


def observe():
    _private('arm-intent.json')
    value = snapshot()
    validate_ready(value, require_drained=False)
    return {'outcome': 'L_NATURAL_PRODUCT_CRON_OBSERVED', 'snapshot': value}


def disarm():
    _private('arm-intent.json')
    intent = STATE / 'disarm-intent.json'
    if intent.exists():
        current_state = snapshot()
        if current_state['schedule']['enabled'] is not False:
            raise ValueError('unknown disarm outcome requires inspection')
        return {'outcome': 'L_NATURAL_PRODUCT_CRON_DISARMED_READBACK',
                'snapshot': current_state}
    freeze(intent, {'scheduleId': SCHEDULE, 'at': datetime.now(timezone.utc).isoformat()})
    status, body = api('PATCH', f'/v1/schedules/{SCHEDULE}', {'enabled': False})
    after = snapshot()
    if status != 200 or after['schedule']['enabled'] is not False:
        raise ValueError('natural schedule disable readback differs')
    result = {'outcome': 'L_NATURAL_PRODUCT_CRON_DISARMED', 'status': status,
              'body': body, 'snapshot': after}
    freeze(STATE / 'disarm-result.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['arm', 'observe', 'disarm'])
    args = parser.parse_args()
    print(json.dumps(globals()[args.phase](), ensure_ascii=False, indent=2, default=str))
