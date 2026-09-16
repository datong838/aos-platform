"""Retire J event-control dispatch after the exact configuration refresh."""
import argparse
import json

import a0v_transaction_successor_business as j
from a0v_j_product_window import policy_profile
from a0v_qyh_current_product_event_first_chain import freeze, freeze_or_match, _approve


STATE = j.STATE / 'event-control-refresh-retirement'
PREFIX = 'a0v-qyh-j-refresh-event-retirement-20260916'
REFRESH_ID = '708dd66a-787c-43b5-be8e-4953e37a24cd'
REFRESH_HASH = 'sha256:4e40226aa22cbceab702225636699cf1b83e1bb11aa77544117c6e31bc50288f'
BUSINESS = (
    'ecommerce_growth_analysis_advance', 'ecommerce_growth_case_put',
    'ecommerce_growth_content_generate', 'ecommerce_growth_content_review',
    'ecommerce_growth_data_fulfill', 'ecommerce_growth_investigation_describe',
    'ecommerce_growth_review_advance', 'ecommerce_growth_schedule_put',
    'ecommerce_growth_schedule_trigger',
)


def load(phase):
    path = STATE / f'{phase}-result.json'
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError('private preceding event retirement result required')
    return json.loads(path.read_text())


def current(phase):
    from a0v_formal_text_model_renewal import database_connect
    policy = policy_profile()
    with database_connect('aos_meta_head')() as conn:
        conn.execute("SELECT set_config('aos.org_id','org-org',true),"
                     "set_config('aos.project_id','dev-project',true)")
        versions = conn.execute('SELECT version_num FROM alembic_version').fetchall()
        runtime = conn.execute("""SELECT * FROM extension_runtime_binding
            WHERE org_id='org-org' AND project_id='dev-project'
              AND installation_id=%s AND generation=%s""", (j.G_ID, j.G_GENERATION)).fetchone()
        dispatch = conn.execute("""SELECT * FROM extension_operation_dispatch_binding
            WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s
            ORDER BY operation_id""", (j.GROUP,)).fetchall()
        schedule = conn.execute("""SELECT * FROM automation_schedule_binding
            WHERE org_id='org-org' AND project_id='dev-project'
              AND installation_id=%s AND generation=%s AND policy_id=%s""",
            (j.G_ID, j.G_GENERATION, policy.POLICY)).fetchone()
        refresh = conn.execute("""SELECT * FROM extension_dispatch_configuration_refresh_receipt
            WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s
            ORDER BY revision DESC LIMIT 1""", (j.GROUP,)).fetchone()
        canary = conn.execute("""SELECT count(*) AS n FROM extension_operation_dispatch_binding
            WHERE org_id='dev-org' AND project_id='dev-project' AND cutover_group_id=%s""",
            (j.GROUP,)).fetchone()['n']
    expected_group = 31 if phase == 'fence' else 32
    business_group = 31 if phase == 'fence' else 32
    control_group = 30 if phase == 'fence' else 32
    rows = {row['operation_id']: row for row in dispatch}
    if (versions != [{'version_num': 'a0v_071'}] or runtime is None
        or runtime['revision'] != 9 or runtime['execution_epoch'] != 5
        or runtime['enabled'] is not True or runtime['operation_fence'] is not False
        or runtime['desired_state'] != 'enabled' or runtime['observed_state'] != 'ready'
        or len(rows) != 10 or set(rows) != set(BUSINESS) | {'ecommerce_growth_event_control'}
        or any(rows[name]['execution_epoch'] != 5 or rows[name]['revision'] != 18
               or rows[name]['operation_fence'] is not False
               or rows[name]['cutover_group_revision'] != business_group for name in BUSINESS)
        or rows['ecommerce_growth_event_control']['execution_epoch'] != 3
        or rows['ecommerce_growth_event_control']['revision'] != (1 if phase == 'fence' else 2)
        or rows['ecommerce_growth_event_control']['operation_fence'] is not (phase == 'shrink')
        or rows['ecommerce_growth_event_control']['cutover_group_revision'] != control_group
        or schedule is None or schedule['enabled'] is not False or schedule['revision'] != 2
        or refresh is None or str(refresh['receipt_id']) != REFRESH_ID
        or refresh['content_hash'] != REFRESH_HASH or refresh['revision'] != 1
        or canary != 0):
        raise ValueError('exact refresh-proven J event retirement state required')
    return dict(
        schemaVersion='aos.ecommerce.event-control-dispatch/v1', phase=phase,
        installationRef=dict(installationId=j.G_ID, revision=5, lockHash=j.LOCK,
                             overlayRevision='a0v-canonical-ecommerce-v1'),
        generation=j.G_GENERATION, executionEpoch=3, runtimeRevision=9,
        cutoverGroupId=j.GROUP, expectedGroupRevision=expected_group,
        caseId=policy.CASE, schedulePolicyId=policy.POLICY,
        idempotencyKey=f'{PREFIX}-{phase}',
    )


def drain():
    from a0v_formal_text_model_renewal import database_connect
    with database_connect('aos_meta_head')() as conn:
        conn.execute("SELECT set_config('aos.org_id','org-org',true),"
                     "set_config('aos.project_id','dev-project',true)")
        running = conn.execute("""SELECT count(*) AS n FROM extension_runtime_execution_attempt
            WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s
              AND generation=%s AND state='running'""", (j.G_ID, j.G_GENERATION)).fetchone()['n']
        claimed = conn.execute("""SELECT count(*) AS n FROM automation_occurrence
            WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s
              AND generation=%s AND execution_epoch=3 AND status='claimed'""",
            (j.G_ID, j.G_GENERATION)).fetchone()['n']
        attempts = [dict(row) for row in conn.execute("""SELECT a.status,count(*) AS count,
              min(a.claim_until) AS min_claim_until,max(a.claim_until) AS max_claim_until
            FROM automation_occurrence_dispatch_attempt a
            JOIN automation_occurrence o USING(org_id,project_id,occurrence_id)
            WHERE a.org_id='org-org' AND a.project_id='dev-project' AND o.installation_id=%s
              AND o.generation=%s AND o.execution_epoch=3 AND a.status IN ('claimed','unknown')
            GROUP BY a.status ORDER BY a.status""", (j.G_ID, j.G_GENERATION)).fetchall()]
    return dict(runningExecutionAttempts=running, claimedOccurrences=claimed,
                unresolvedDispatchAttempts=sum(row['count'] for row in attempts), attempts=attempts)


def run(phase):
    intent = STATE / f'{phase}-intent.json'
    if intent.exists() and phase not in ('approve-fence', 'approve-shrink'):
        raise ValueError('existing event retirement intent requires read-only inspection')
    plane = j.setup()
    if phase in ('approve-fence', 'approve-shrink'):
        target = phase.removeprefix('approve-')
        if target == 'shrink':
            load('fence')
        request = current(target)
        policy = policy_profile()
        payload = dict(caseId=policy.CASE, schedulePolicyId=policy.POLICY,
                       dispatchIntent=request)
        freeze_or_match(intent, payload)
        bundle, approval = _approve('ecommerce_growth_event_dispatch', payload,
                                    f'{PREFIX}-{target}-approval')
        result = dict(request=request, approvalRef=approval, proposalId=bundle.proposal.id)
    elif phase in ('fence', 'shrink'):
        from aos_api.ecommerce_event_control_dispatch_lifecycle import EventControlDispatchRequest
        from aos_api.tenant_scope import TenantScope
        approved = load(f'approve-{phase}')
        if current(phase) != approved['request']:
            raise ValueError('approved event retirement state drifted')
        if phase == 'shrink' and drain()['unresolvedDispatchAttempts']:
            raise ValueError('event retirement dispatch attempts remain unresolved')
        request = EventControlDispatchRequest.model_validate(
            {**approved['request'], 'approvalRef': approved['approvalRef']})
        freeze(intent, request.wire())
        scope = TenantScope('org-org', 'dev-project')
        service = plane.pipeline_control_factory.build_event_dispatch_lifecycle(scope)
        receipt = service.transition(scope=scope, request=request, actor=j.ACTOR)
        replay = service.transition(scope=scope, request=request, actor=j.ACTOR)
        if receipt['receiptId'] != replay['receiptId'] or replay['replayed'] is not True:
            raise ValueError('event retirement replay differs')
        result = dict(receipt=receipt, replayReceiptId=replay['receiptId'], sameKeyReplay=True)
    elif phase == 'inspect-drain':
        load('fence')
        freeze(intent, dict(phase=phase, installationId=j.G_ID, generation=j.G_GENERATION,
                            executionEpoch=3))
        result = drain()
    else:
        raise ValueError('unsupported event retirement phase')
    freeze(STATE / f'{phase}-result.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('approve-fence', 'fence', 'inspect-drain',
                                         'approve-shrink', 'shrink'))
    args = parser.parse_args()
    print(json.dumps(run(args.phase), ensure_ascii=False, default=str))
