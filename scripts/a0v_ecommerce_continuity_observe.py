"""Read actual reinstall leases and OCI liveness, without renewing or invoking."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
RECOVERY = ROOT.parent/'.aos-recovery-20260912'


def container_observation(container_id):
    if not isinstance(container_id,str) or not container_id:
        return 'unavailable'
    try:
        result=subprocess.run(['docker','--context','colima-aos-extension','inspect',
            '--format','{{.State.Running}}',container_id],capture_output=True,text=True,timeout=15)
    except (subprocess.TimeoutExpired,OSError):
        return 'unavailable'
    if result.returncode != 0:
        return 'unavailable'
    return {'true':'running','false':'stopped'}.get(result.stdout.strip(),'unavailable')


def current_preparation(conn,installation,*,org_id,project_id):
    rows=conn.execute("""SELECT o.operation_id,o.created_at,o.deadline,o.status
        FROM extension_runtime_operation o
        WHERE o.org_id=%s AND o.project_id=%s AND o.installation_id=%s
          AND o.kind='runtime-apply' AND EXISTS (
            SELECT 1 FROM extension_runtime_resource_lease r
            JOIN extension_runtime_binding b ON b.org_id=r.org_id AND b.project_id=r.project_id
              AND b.generation=r.generation AND b.installation_id=o.installation_id
            WHERE r.org_id=o.org_id AND r.project_id=o.project_id AND r.operation_id=o.operation_id)
        ORDER BY o.operation_id""",(org_id,project_id,installation)).fetchall()
    if len(rows)!=1:raise ValueError('exact current preparation required')
    return rows[0]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--successor-1-7',action='store_true')
    group.add_argument('--after-config-recovery',action='store_true')
    group.add_argument('--after-sleep-recovery',action='store_true')
    group.add_argument('--niushop-1-4',action='store_true')
    args=parser.parse_args()
    spec=importlib.util.spec_from_file_location('first',ROOT/'scripts/a0v_canonical_ecommerce_first_install.py')
    first=importlib.util.module_from_spec(spec);spec.loader.exec_module(first)
    connect=first.container_database_connect_factory(context='colima-aos-extension',container='aos-a0v-recovery-pg',database_name='aos_meta_head')
    state='state/ecommerce-1.7-first-install.json' if args.successor_1_7 else 'state/ecommerce-1.6-reinstall.json'
    if args.after_config_recovery:state='state/ecommerce-1.7-recovered-first-install.json'
    if args.after_sleep_recovery:state='state/ecommerce-1.7-sleep-recovered-first-install.json'
    if args.niushop_1_4:state='state/niushop-1.4-first-install.json'
    installation=json.loads((RECOVERY/state).read_text())['installationId']
    with connect() as conn:
        now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        if args.niushop_1_4:
            operation=current_preparation(conn,installation,org_id='org-org',project_id='dev-project')
        else:
            operation=conn.execute("SELECT operation_id,created_at,deadline,status FROM extension_runtime_operation WHERE installation_id=%s AND kind='runtime-apply'",(installation,)).fetchall()
            if len(operation)!=1:raise ValueError('exact reinstall operation required')
            operation=operation[0]
        events=conn.execute("SELECT occurred_at,payload FROM extension_runtime_event WHERE operation_id=%s AND type='runtime_lease_renewed' ORDER BY sequence",(operation['operation_id'],)).fetchall()
        resources=conn.execute("SELECT resource_id,generation,container_id,cleanup_state,observed_release,expires_at FROM extension_runtime_resource_lease WHERE operation_id=%s ORDER BY resource_id",(operation['operation_id'],)).fetchall()
        bindings=conn.execute("SELECT generation,observed_state,desired_state,enabled,operation_fence,revision,config_ref FROM extension_runtime_binding WHERE installation_id=%s",(installation,)).fetchall()
        canary=conn.execute("SELECT count(*) AS n FROM bundle_installation WHERE org_id='dev-org' AND project_id='dev-project'").fetchone()['n']
        fenced_configuration=False
        if (args.after_config_recovery or args.after_sleep_recovery or args.niushop_1_4) and len(bindings)==1 and bindings[0]['observed_state']=='unknown':
            import sys
            sys.path.insert(0,str(ROOT/'services/aos-api'))
            from aos_api.extension_runtime.lease_renewal import _configuration_transition_owned
            fenced_configuration=_configuration_transition_owned(conn,target=('org-org','dev-project',installation),generation=bindings[0]['generation'],binding=bindings[0])
    observations=[container_observation(row['container_id']) for row in resources]
    alive=[value=='running' for value in observations]
    valid=(len(resources)==3 and all(alive) and canary==0 and len(bindings)==1
        and (bindings[0]['observed_state']=='ready' or fenced_configuration) and all(row['generation']==bindings[0]['generation']
        and not row['observed_release'] and row['cleanup_state']=='pending' and row['expires_at']>now for row in resources))
    crossed=now>operation['deadline']
    outcome='CONTINUITY_CROSS_INITIAL_DEADLINE_GREEN' if valid and crossed and len(events)>=3 else 'CONTINUITY_OBSERVING' if valid else 'CONTINUITY_FAILED'
    if fenced_configuration and valid:outcome='CONFIGURED_FENCED_'+outcome
    result=dict(outcome=outcome,fencedConfigurationProven=fenced_configuration,installationId=installation,observedAt=now,originalDeadline=operation['deadline'],
        elapsedSeconds=(now-operation['created_at']).total_seconds(),renewalCount=len(events),renewals=events,
        resources=resources,containersRunning=alive,containerObservations=observations,
        bindings=bindings,canaryInstallationCount=canary)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,default=str,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in {'resources','renewals'}},default=str,indent=2))


if __name__=='__main__':main()
