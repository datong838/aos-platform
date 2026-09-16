"""Read-only exact verification of the completed N successor cutover."""
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/aos-api'));sys.path.insert(0,str(ROOT/'scripts'))

import a0v_m_reinstall_recovery as recovery
import a0v_n_successor_business as successor
import a0v_n_successor_cutover as cutover
from a0v_formal_text_model_renewal import database_connect
from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS

HOST_STATUS=ROOT.parent/'.aos-recovery-20260916/state/original-transaction-recovery/install/recovery-n/runtime-host-status.json'
EVIDENCE=ROOT/'.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/sc4-5l6y5f4-w-final-state.json'


def _pid_alive(pid):
    try:os.kill(pid,0);return True
    except OSError:return False


def validate(value):
    installation=value['installation'];head=installation['head'];binding=installation['bindings']
    if (str(head['installation_id'])!=successor.N_ID or head['etag_version']!=5
        or head['state']!='active' or head['lock_hash']!=successor.LOCK
        or len(binding)!=1 or str(binding[0]['generation'])!=successor.N_GENERATION
        or binding[0]['revision']!=6 or binding[0]['execution_epoch']!=3
        or binding[0]['enabled'] is not True or binding[0]['operation_fence'] is not False
        or binding[0]['desired_state']!='enabled' or binding[0]['observed_state']!='ready'
        or binding[0]['config_ref']!=successor.CONFIG
        or len(installation['resources'])!=3
        or any(row['cleanup_state']!='pending' or row['observed_release'] is not False
               for row in installation['resources'])
        or len(installation['operations'])!=4
        or any(row['status']!='succeeded' for row in installation['operations'])
        or installation['canaryInstallations']!=0):
        raise ValueError('exact post-cutover N installation required')
    database=value['database'];routes=database['routes']
    if (database['version']!=[{'version_num':'a0v_074'}]
        or len(routes)!=len(ECOMMERCE_GROWTH_OPERATIONS)
        or [row['operation_id'] for row in routes]!=sorted(ECOMMERCE_GROWTH_OPERATIONS)
        or any(row['handler_kind']!='extension' or str(row['installation_id'])!=successor.N_ID
               or str(row['generation'])!=successor.N_GENERATION or row['execution_epoch']!=3
               or row['operation_fence'] is not False or row['revision']!=24
               or row['cutover_group_revision']!=42 for row in routes)
        or database['inflight']!={'running':0,'unresolved':0}
        or any(row['enabled'] is not False for row in database['scheduleBindings'])
        or any(row['enabled'] is not False for row in database['policyHeads'])
        or database['postCutoverRuns']!=0 or database['negativeCanaryInstallations']!=0):
        raise ValueError('exact post-cutover database state required')
    history=value['cutoverHistory'];registration=value['registration']
    registration_ref=history['activationReceipts']['prepare']['registrationReceiptRef']
    if (history['observedStatus']!='resumed' or history['rollbacks']!=[]
        or set(history['activationReceipts'])!={'prepare','pause','commit','validate','resume'}
        or registration['receipt']['receiptId']!=registration_ref['resourceId']
        or registration['receipt']['contentHash']!=registration_ref['contentHash']):
        raise ValueError('exact N registration and resumed history required')
    host=value['runtimeHost'];targets=host.get('liveTargets') or []
    if (host.get('outcome')!='RUNTIME_HOST_ACTIVE' or host.get('tenantCount')!=1
        or host.get('canaryTenantCount')!=0 or not value['runtimeHostPidAlive']
        or len(targets)!=1 or targets[0].get('installationId')!=successor.N_ID
        or targets[0].get('generation')!=successor.N_GENERATION
        or targets[0].get('tenant')!=['org-org','dev-project']):
        raise ValueError('exact live single N Runtime Host target required')
    return value


def observe():
    current=recovery.profile();installation=current.observe_installation(successor.N_ID)
    resume=cutover.load('resume')['receipt']
    with database_connect('aos_meta_head')() as conn:
        routes=[dict(row) for row in conn.execute('''SELECT operation_id,handler_kind,
          installation_id,generation,execution_epoch,operation_fence,revision,cutover_group_revision
          FROM extension_operation_dispatch_binding WHERE org_id='org-org' AND project_id='dev-project'
          AND cutover_group_id=%s ORDER BY operation_id''',(successor.GROUP,)).fetchall()]
        database={'version':[dict(row) for row in conn.execute('SELECT version_num FROM alembic_version').fetchall()],
          'routes':routes,
          'inflight':dict(conn.execute('''SELECT
            (SELECT count(*) FROM extension_runtime_execution_attempt WHERE org_id='org-org'
              AND project_id='dev-project' AND installation_id=%s AND generation=%s AND state='running') running,
            (SELECT count(*) FROM automation_occurrence_dispatch_attempt a JOIN automation_occurrence o
              USING(org_id,project_id,occurrence_id) WHERE a.org_id='org-org' AND a.project_id='dev-project'
              AND o.installation_id=%s AND o.generation=%s AND a.status IN ('claimed','unknown')) unresolved''',
              (successor.N_ID,successor.N_GENERATION,successor.N_ID,successor.N_GENERATION)).fetchone()),
          'scheduleBindings':[dict(row) for row in conn.execute('''SELECT policy_id,policy_revision,
            installation_id,generation,execution_epoch,enabled,approved,effective_until,revision
            FROM automation_schedule_binding WHERE org_id='org-org' AND project_id='dev-project'
            ORDER BY policy_id,policy_revision''').fetchall()],
          'policyHeads':[dict(row) for row in conn.execute('''SELECT schedule_policy_id,current_revision,enabled
            FROM ecommerce_investigation_schedule_policy_head WHERE org_id='org-org' AND project_id='dev-project'
            ORDER BY schedule_policy_id''').fetchall()],
          'postCutoverRuns':conn.execute('''SELECT count(*) AS n FROM meta_schedule_run
            WHERE org_id='org-org' AND project_id='dev-project' AND started_at >= %s''',
            (resume['createdAt'],)).fetchone()['n'],
          'negativeCanaryInstallations':conn.execute("""SELECT count(*) AS n FROM bundle_installation
            WHERE org_id='dev-org' AND project_id='dev-project'""").fetchone()['n']}
    host=json.loads(HOST_STATUS.read_text())
    value={'outcome':'N_SUCCESSOR_NINE_ROUTE_CUTOVER_GREEN','installation':installation,
      'database':database,'registration':json.loads((successor.STATE/'register-result.json').read_text()),
      'cutoverHistory':successor.setup().ecommerce_growth_cutover_service.read_activation_history(
        scope=__import__('aos_api.tenant_scope',fromlist=['TenantScope']).TenantScope('org-org','dev-project'),
        installation_id=successor.N_ID,idempotency_key=cutover.PREFIX+'-prepare',actor=successor.ACTOR),
      'runtimeHost':host,'runtimeHostPidAlive':_pid_alive(host['pid']),
      'externalEffects':0,'businessRunsResumed':0}
    return validate(value)


def main():
    value=observe();EVIDENCE.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+'\n')
    print(json.dumps(value,ensure_ascii=False,indent=2,default=str))


if __name__=='__main__':main()
