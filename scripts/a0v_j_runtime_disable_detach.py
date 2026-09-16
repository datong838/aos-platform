"""Disable and detach the nine refreshed J business dispatch paths."""
import argparse
import json
from uuid import UUID

import a0v_transaction_successor_business as j
from a0v_qyh_current_product_event_first_chain import freeze, freeze_or_match


STATE = j.STATE / 'runtime-disable-detach-after-refresh'
KEY = 'a0v-qyh-j-runtime-disable-after-refresh-20260916'
REFRESH_ID = '708dd66a-787c-43b5-be8e-4953e37a24cd'
REFRESH_HASH = 'sha256:4e40226aa22cbceab702225636699cf1b83e1bb11aa77544117c6e31bc50288f'
OPERATION_ID = UUID('178a52b9-b8db-4b35-9c0a-66288bd703c8')


def observe():
    from a0v_formal_text_model_renewal import database_connect
    from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
    with database_connect('aos_meta_head')() as conn:
        conn.execute("SELECT set_config('aos.org_id','org-org',true),"
                     "set_config('aos.project_id','dev-project',true)")
        head = conn.execute("""SELECT i.etag_version,r.state,r.lock_hash,r.overlay_revision
            FROM bundle_installation i JOIN bundle_installation_revision r
              ON r.org_id=i.org_id AND r.project_id=i.project_id
             AND r.installation_pk=i.installation_pk AND r.revision=i.current_revision
            WHERE i.org_id='org-org' AND i.project_id='dev-project' AND i.installation_id=%s""",
            (j.G_ID,)).fetchone()
        runtime = conn.execute("""SELECT * FROM extension_runtime_binding
            WHERE org_id='org-org' AND project_id='dev-project'
              AND installation_id=%s AND generation=%s""", (j.G_ID, j.G_GENERATION)).fetchone()
        dispatch = [dict(row) for row in conn.execute("""SELECT * FROM extension_operation_dispatch_binding
            WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s
            ORDER BY operation_id""", (j.GROUP,)).fetchall()]
        refresh = conn.execute("""SELECT receipt_id,revision,content_hash FROM
            extension_dispatch_configuration_refresh_receipt
            WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s
            ORDER BY revision DESC LIMIT 1""", (j.GROUP,)).fetchone()
        operation = conn.execute("""SELECT operation_id,installation_id,kind,
            expected_binding_revision,status,phase,revision,request_hash,requested_by
            FROM extension_runtime_operation WHERE org_id='org-org' AND project_id='dev-project'
              AND operation_id=%s""", (OPERATION_ID,)).fetchone()
        lifecycle = dict(conn.execute("""SELECT
            (SELECT count(*) FROM extension_dispatch_lifecycle_operation WHERE org_id='org-org'
              AND project_id='dev-project' AND runtime_operation_id=%s) AS operations,
            (SELECT count(*) FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org'
              AND project_id='dev-project' AND runtime_operation_id=%s) AS receipts""",
            (OPERATION_ID, OPERATION_ID)).fetchone())
        inflight = dict(conn.execute("""SELECT
            (SELECT count(*) FROM extension_runtime_execution_attempt WHERE org_id='org-org'
              AND project_id='dev-project' AND installation_id=%s AND generation=%s AND state='running') AS running,
            (SELECT count(*) FROM automation_occurrence_dispatch_attempt a JOIN automation_occurrence o
              USING(org_id,project_id,occurrence_id) WHERE a.org_id='org-org' AND a.project_id='dev-project'
              AND o.installation_id=%s AND o.generation=%s AND a.status IN ('claimed','unknown')) AS unresolved""",
            (j.G_ID, j.G_GENERATION, j.G_ID, j.G_GENERATION)).fetchone())
        canary = conn.execute("""SELECT count(*) AS n FROM extension_runtime_binding
            WHERE org_id='dev-org' AND project_id='dev-project' AND installation_id=%s""",
            (j.G_ID,)).fetchone()['n']
        version = conn.execute('SELECT version_num FROM alembic_version').fetchall()
    return dict(version=version, head=None if head is None else dict(head),
                runtime=None if runtime is None else dict(runtime), dispatch=dispatch,
                refresh=None if refresh is None else dict(refresh), inflight=inflight,
                operation=None if operation is None else dict(operation), lifecycle=lifecycle,
                canary=canary, operations=sorted(ECOMMERCE_GROWTH_OPERATIONS))


def require_enabled(snapshot):
    head, runtime, rows, refresh = (snapshot['head'], snapshot['runtime'],
                                    snapshot['dispatch'], snapshot['refresh'])
    if (snapshot['version'] != [{'version_num': 'a0v_071'}] or head is None or runtime is None
        or head != {'etag_version': 5, 'state': 'active', 'lock_hash': j.LOCK,
                    'overlay_revision': 'a0v-canonical-ecommerce-v1'}
        or runtime['revision'] != 9 or runtime['execution_epoch'] != 5
        or runtime['enabled'] is not True or runtime['operation_fence'] is not False
        or runtime['desired_state'] != 'enabled' or runtime['observed_state'] != 'ready'
        or len(rows) != 9 or [row['operation_id'] for row in rows] != snapshot['operations']
        or any(row['handler_kind'] != 'extension' or str(row['installation_id']) != j.G_ID
               or str(row['generation']) != j.G_GENERATION or row['execution_epoch'] != 5
               or row['revision'] != 18 or row['operation_fence'] is not False
               or row['cutover_group_revision'] != 33 for row in rows)
        or refresh is None or str(refresh['receipt_id']) != REFRESH_ID
        or refresh['revision'] != 1 or refresh['content_hash'] != REFRESH_HASH
        or snapshot['inflight'] != {'running': 0, 'unresolved': 0} or snapshot['canary'] != 0):
        raise ValueError('exact drained refreshed J runtime required')
    return dict(generation=j.G_GENERATION, bindingRevision=9)


def preflight():
    target = require_enabled(observe())
    result = dict(outcome='J_REFRESHED_RUNTIME_DISABLE_PREFLIGHT_GREEN', target=target,
                  externalEffects=0, businessRunsResumed=0)
    freeze(STATE / 'preflight-result.json', result)
    return result


def require_recovery(snapshot):
    runtime, rows, operation = snapshot['runtime'], snapshot['dispatch'], snapshot['operation']
    if (snapshot['version'] != [{'version_num': 'a0v_072'}] or runtime is None
        or runtime['revision'] != 11 or runtime['execution_epoch'] != 6
        or runtime['enabled'] is not False or runtime['operation_fence'] is not True
        or runtime['desired_state'] != 'disabled' or runtime['observed_state'] != 'unknown'
        or operation is None or operation['operation_id'] != OPERATION_ID
        or str(operation['installation_id']) != j.G_ID or operation['kind'] != 'disable'
        or operation['expected_binding_revision'] != 9 or operation['status'] != 'succeeded'
        or operation['phase'] != 'succeeded' or operation['requested_by'] != j.ACTOR
        or snapshot['lifecycle'] != {'operations': 0, 'receipts': 0}
        or len(rows) != 9 or [row['operation_id'] for row in rows] != snapshot['operations']
        or any(row['handler_kind'] != 'extension' or str(row['installation_id']) != j.G_ID
               or str(row['generation']) != j.G_GENERATION or row['execution_epoch'] != 5
               or row['revision'] != 18 or row['operation_fence'] is not False
               or row['cutover_group_revision'] != 33 for row in rows)
        or snapshot['inflight'] != {'running': 0, 'unresolved': 0} or snapshot['canary'] != 0):
        raise ValueError('exact succeeded-disable callback recovery state required')
    return snapshot


def require_recovered(snapshot):
    rows = snapshot['dispatch']
    if (snapshot['version'] != [{'version_num': 'a0v_072'}]
        or snapshot['runtime'] is None or snapshot['runtime']['revision'] != 11
        or snapshot['runtime']['execution_epoch'] != 6
        or snapshot['runtime']['enabled'] is not False
        or snapshot['runtime']['operation_fence'] is not True
        or snapshot['runtime']['desired_state'] != 'disabled'
        or snapshot['runtime']['observed_state'] != 'unknown'
        or snapshot['lifecycle'] != {'operations': 1, 'receipts': 2}
        or len(rows) != 9 or [row['operation_id'] for row in rows] != snapshot['operations']
        or any(row['handler_kind'] != 'legacy' or row['installation_id'] is not None
               or row['generation'] is not None or row['execution_epoch'] is not None
               or row['operation_fence'] is not True or row['revision'] != 20
               or row['cutover_group_revision'] != 35 for row in rows)
        or snapshot['inflight'] != {'running': 0, 'unresolved': 0} or snapshot['canary'] != 0):
        raise ValueError('exact recovered disable/detach state required')
    return snapshot


def recover():
    current = observe()
    already_recovered = current['lifecycle'] == {'operations': 1, 'receipts': 2}
    before = require_recovered(current) if already_recovered else require_recovery(current)
    freeze_or_match(STATE / 'recovery-intent.json', dict(
        runtimeOperationId=str(OPERATION_ID), runtimeRevision=before['runtime']['revision'],
        runtimeEpoch=before['runtime']['execution_epoch'], dispatchGroupRevision=33,
        externalEffectsAllowed=False, resendDisable=False))
    plane = j.setup()
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    scope = {'org_id': 'org-org', 'project_id': 'dev-project'}
    with consumer_connection(runtime_worker_connection, scope) as conn:
        fence, detach = plane.disable_dependent.recover_succeeded_disable(
            conn, org_id=scope['org_id'], project_id=scope['project_id'],
            runtime_operation_id=OPERATION_ID)
        replay_fence, replay_detach = plane.disable_dependent.recover_succeeded_disable(
            conn, org_id=scope['org_id'], project_id=scope['project_id'],
            runtime_operation_id=OPERATION_ID)
    after = observe()
    rows = after['dispatch']
    if (after['runtime'] != before['runtime'] or after['inflight'] != {'running': 0, 'unresolved': 0}
        or after['canary'] != 0 or after['lifecycle'] != {'operations': 1, 'receipts': 2}
        or len(rows) != 9 or any(row['handler_kind'] != 'legacy'
            or row['installation_id'] is not None or row['generation'] is not None
            or row['operation_fence'] is not True or row['revision'] != 20
            or row['cutover_group_revision'] != 35 for row in rows)
        or not replay_fence.replayed or replay_fence.receipt_id != fence.receipt_id
        or not replay_detach.replayed or replay_detach.receipt_id != detach.receipt_id):
        raise ValueError('succeeded-disable recovery readback differs')
    result = dict(outcome='J_SUCCEEDED_RUNTIME_DISABLE_CALLBACK_RECOVERED',
        operationId=str(OPERATION_ID), resendDisable=False,
        recoveredBeforeReadback=already_recovered,
        fence=fence.model_dump(mode='json', by_alias=True),
        detach=detach.model_dump(mode='json', by_alias=True),
        replay=dict(fenceReceiptId=str(replay_fence.receipt_id),
                    detachReceiptId=str(replay_detach.receipt_id)),
        final=dict(runtimeRevision=after['runtime']['revision'],
                   runtimeEpoch=after['runtime']['execution_epoch'],
                   dispatchHandler='legacy', dispatchRevision=20,
                   dispatchGroupRevision=35, lifecycle=after['lifecycle']),
        externalEffects=0, businessRunsResumed=0)
    freeze(STATE / 'execute-result.json', result)
    return result


def execute():
    path = STATE / 'preflight-result.json'
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError('private disable preflight required')
    target = require_enabled(observe())
    intent = dict(installationId=j.G_ID, installationEtag=5, target=target,
                  actor=j.ACTOR, idempotencyKey=KEY)
    freeze(STATE / 'execute-intent.json', intent)
    plane = j.setup()
    receipt = plane.disable_service.request(
        org_id='org-org', project_id='dev-project', installation_id=j.G_ID,
        actor=j.ACTOR, roles=frozenset({'admin'}), markings=frozenset(),
        idempotency_key=KEY, if_match='"5"', target=target)
    operation_id = UUID(receipt.response_json['operationId'])
    from aos_api.asset_registry.control_policy import DISABLE_RUNTIME_OPERATION
    from aos_api.extension_runtime.current_permission import CurrentControlPermission
    from aos_api.extension_runtime.disable_consumer import ClaimedDisableDelivery, RuntimeDisableConsumer
    from aos_api.extension_runtime.generation_attempts import GenerationDrainReader
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.tenant_scope import TenantScope
    consumer = RuntimeDisableConsumer(connect=runtime_worker_connection,
        installation_store=plane.installation_store,
        check_current_permission=CurrentControlPermission(operation=DISABLE_RUNTIME_OPERATION),
        check_drained=GenerationDrainReader(), dependent=plane.disable_dependent)
    scope = TenantScope('org-org', 'dev-project')
    with consumer._connection({'org_id': scope.org_id, 'project_id': scope.project_id}) as conn:
        lease = consumer.outbox.claim(conn, org_id=scope.org_id, project_id=scope.project_id,
                                     operation_kind='disable', installation_id=j.G_ID)
    if lease is None or lease.operation_id != operation_id:
        raise ValueError('exact J disable delivery required')
    delivery = consumer.finish_claimed(ClaimedDisableDelivery(scope, lease, UUID(j.G_ID)))
    if delivery.operation_id != operation_id or delivery.operation_status != 'succeeded':
        raise ValueError('J disable did not settle')
    replay = plane.disable_service.request(
        org_id='org-org', project_id='dev-project', installation_id=j.G_ID,
        actor=j.ACTOR, roles=frozenset({'admin'}), markings=frozenset(),
        idempotency_key=KEY, if_match='"5"', target=target)
    if replay.response_json != receipt.response_json or replay.replayed is not True:
        raise ValueError('J disable same-key replay differs')
    with consumer._connection({'org_id': scope.org_id, 'project_id': scope.project_id}) as conn:
        detached = plane.disable_dependent.after_runtime_disabled(conn, org_id=scope.org_id,
            project_id=scope.project_id, runtime_operation_id=operation_id)
        conn.commit()
    if detached is None or detached.replayed is not True:
        raise ValueError('J detach Receipt replay required')
    result = dict(outcome='J_REFRESHED_RUNTIME_DISABLED_DETACHED',
        operationId=str(operation_id), requestReceipt=receipt.response_json,
        sameKeyReplay=True, delivery=dict(operationStatus=delivery.operation_status,
            deliveryStatus=delivery.delivery_status), detachReplay=detached.model_dump(mode='json', by_alias=True))
    freeze(STATE / 'execute-result.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('preflight', 'execute', 'recover'))
    args = parser.parse_args()
    print(json.dumps(globals()[args.mode](), ensure_ascii=False, default=str))
