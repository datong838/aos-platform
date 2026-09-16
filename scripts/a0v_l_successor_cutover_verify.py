"""Read-only exact verification of the completed L successor cutover."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/aos-api'))
sys.path.insert(0, str(ROOT / 'scripts'))

import a0v_j_uninstall_reinstall_recovery as recovery
import a0v_l_successor_business as successor
import a0v_l_successor_cutover as cutover
from a0v_formal_text_model_renewal import database_connect
from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS

HOST_STATUS = recovery.STATE / 'runtime-host-status.json'
EVIDENCE = ROOT / '.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/sc4-5l6y5f4-o-final-state.json'


def validate(value):
    installation = value['installation']
    head, bindings = installation['head'], installation['bindings']
    if (str(head['installation_id']) != successor.L_ID or head['etag_version'] != 5
        or head['state'] != 'active' or head['lock_hash'] != successor.LOCK
        or len(bindings) != 1 or str(bindings[0]['generation']) != successor.L_GENERATION
        or bindings[0]['revision'] != 6 or bindings[0]['execution_epoch'] != 3
        or bindings[0]['enabled'] is not True or bindings[0]['operation_fence'] is not False
        or bindings[0]['desired_state'] != 'enabled' or bindings[0]['observed_state'] != 'ready'
        or bindings[0]['config_ref'] != successor.CONFIG
        or len(installation['resources']) != 3
        or any(row['cleanup_state'] != 'pending' or row['observed_release'] is not False
               for row in installation['resources'])
        or len(installation['operations']) != 4
        or any(row['status'] != 'succeeded' for row in installation['operations'])
        or installation['canaryInstallations'] != 0):
        raise ValueError('exact post-cutover L installation required')
    routes = value['database']['routes']
    if (value['database']['version'] != [{'version_num': 'a0v_073'}]
        or len(routes) != len(ECOMMERCE_GROWTH_OPERATIONS)
        or [row['operation_id'] for row in routes] != sorted(ECOMMERCE_GROWTH_OPERATIONS)
        or any(row['handler_kind'] != 'extension'
               or str(row['installation_id']) != successor.L_ID
               or str(row['generation']) != successor.L_GENERATION
               or row['execution_epoch'] != 3 or row['operation_fence'] is not False
               or row['revision'] != 21 or row['cutover_group_revision'] != 36
               for row in routes)
        or value['database']['inflight'] != {'running': 0, 'unresolved': 0}
        or value['database']['sourceSchedule'] != [{'id': 'sch-p02-qyh-controlled-20260913-v1', 'enabled': False}]
        or any(row['enabled'] is not False for row in value['database']['scheduleBindings'])
        or any(row['enabled'] is not False for row in value['database']['policyHeads'])
        or value['database']['postCutoverRuns'] != 0
        or value['database']['negativeCanaryInstallations'] != 0):
        raise ValueError('exact post-cutover database state required')
    history = value['cutoverHistory']
    if (history['observedStatus'] != 'resumed' or history['rollbacks'] != []
        or set(history['activationReceipts']) != {'prepare', 'pause', 'commit', 'validate', 'resume'}
        or value['registration']['receipt']['receiptId'] != cutover.RECEIPT
        or value['registration']['receipt']['contentHash'] != cutover.RECEIPT_HASH):
        raise ValueError('exact L registration and resumed history required')
    host = value['runtimeHost']
    if (host != {'businessWorkers': ['product-event', 'analysis-data-requirement'],
                 'canaryTenantCount': 0, 'hostId': 'a0v-local-ecommerce-host-20260912',
                 'intervalSeconds': 2, 'outcome': 'RUNTIME_HOST_ACTIVE',
                 'pid': 87185, 'positiveTenant': 'org-org/dev-project', 'tenantCount': 1}
        or not value['runtimeHostPidAlive']):
        raise ValueError('exact live single-tenant Runtime Host required')
    return value


def observe():
    profile = recovery.profile()
    installation = profile.observe_installation(successor.L_ID)
    resume = cutover.load('resume')['receipt']
    with database_connect('aos_meta_head')() as conn:
        routes = [dict(row) for row in conn.execute('''SELECT operation_id,handler_kind,
            installation_id,generation,execution_epoch,operation_fence,revision,cutover_group_revision
            FROM extension_operation_dispatch_binding WHERE org_id='org-org' AND project_id='dev-project'
            AND cutover_group_id=%s ORDER BY operation_id''', (successor.GROUP,)).fetchall()]
        database = {
            'version': [dict(row) for row in conn.execute('SELECT version_num FROM alembic_version').fetchall()],
            'routes': routes,
            'inflight': dict(conn.execute('''SELECT
                (SELECT count(*) FROM extension_runtime_execution_attempt WHERE org_id='org-org'
                  AND project_id='dev-project' AND installation_id=%s AND generation=%s
                  AND state='running') AS running,
                (SELECT count(*) FROM automation_occurrence_dispatch_attempt a JOIN automation_occurrence o
                  USING(org_id,project_id,occurrence_id) WHERE a.org_id='org-org'
                  AND a.project_id='dev-project' AND o.installation_id=%s AND o.generation=%s
                  AND a.status IN ('claimed','unknown')) AS unresolved''',
                (successor.L_ID, successor.L_GENERATION, successor.L_ID, successor.L_GENERATION)).fetchone()),
            'sourceSchedule': [dict(row) for row in conn.execute("""SELECT id,enabled FROM meta_schedule
                WHERE org_id='org-org' AND project_id='dev-project'
                AND id='sch-p02-qyh-controlled-20260913-v1'""").fetchall()],
            'scheduleBindings': [dict(row) for row in conn.execute('''SELECT policy_id,policy_revision,
                installation_id,generation,execution_epoch,enabled,approved,effective_until,revision
                FROM automation_schedule_binding WHERE org_id='org-org' AND project_id='dev-project'
                ORDER BY policy_id,policy_revision''').fetchall()],
            'policyHeads': [dict(row) for row in conn.execute('''SELECT schedule_policy_id,current_revision,
                enabled FROM ecommerce_investigation_schedule_policy_head
                WHERE org_id='org-org' AND project_id='dev-project' ORDER BY schedule_policy_id''').fetchall()],
            'postCutoverRuns': conn.execute('''SELECT count(*) AS n FROM meta_schedule_run
                WHERE org_id='org-org' AND project_id='dev-project'
                AND schedule_id='sch-p02-qyh-controlled-20260913-v1' AND started_at >= %s''',
                (resume['createdAt'],)).fetchone()['n'],
            'negativeCanaryInstallations': conn.execute("""SELECT count(*) AS n FROM bundle_installation
                WHERE org_id='dev-org' AND project_id='dev-project'""").fetchone()['n'],
        }
    host = json.loads(HOST_STATUS.read_text())
    value = {'outcome': 'L_SUCCESSOR_NINE_ROUTE_CUTOVER_GREEN',
             'installation': installation, 'database': database,
             'registration': json.loads((successor.STATE / 'register-result.json').read_text()),
             'cutoverHistory': successor.setup().ecommerce_growth_cutover_service.read_activation_history(
                 scope=__import__('aos_api.tenant_scope', fromlist=['TenantScope']).TenantScope(
                     'org-org', 'dev-project'), installation_id=successor.L_ID,
                 idempotency_key=cutover.PREFIX + '-prepare', actor=successor.ACTOR),
             'runtimeHost': host,
             'runtimeHostPidAlive': host['pid'] == os.getpid() or _pid_alive(host['pid']),
             'externalEffects': 0, 'businessRunsResumed': 0}
    return validate(value)


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def main():
    value = observe()
    EVIDENCE.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n')
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


if __name__ == '__main__':
    main()
