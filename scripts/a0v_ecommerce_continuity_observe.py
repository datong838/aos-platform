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


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--successor-1-7',action='store_true')
    args=parser.parse_args()
    spec=importlib.util.spec_from_file_location('first',ROOT/'scripts/a0v_canonical_ecommerce_first_install.py')
    first=importlib.util.module_from_spec(spec);spec.loader.exec_module(first)
    connect=first.container_database_connect_factory(context='colima-aos-extension',container='aos-a0v-recovery-pg',database_name='aos_meta_head')
    state='state/ecommerce-1.7-first-install.json' if args.successor_1_7 else 'state/ecommerce-1.6-reinstall.json'
    installation=json.loads((RECOVERY/state).read_text())['installationId']
    with connect() as conn:
        now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        operation=conn.execute("SELECT operation_id,created_at,deadline,status FROM extension_runtime_operation WHERE installation_id=%s AND kind='runtime-apply'",(installation,)).fetchall()
        if len(operation)!=1:raise ValueError('exact reinstall operation required')
        operation=operation[0]
        events=conn.execute("SELECT occurred_at,payload FROM extension_runtime_event WHERE operation_id=%s AND type='runtime_lease_renewed' ORDER BY sequence",(operation['operation_id'],)).fetchall()
        resources=conn.execute("SELECT resource_id,generation,container_id,cleanup_state,observed_release,expires_at FROM extension_runtime_resource_lease WHERE operation_id=%s ORDER BY resource_id",(operation['operation_id'],)).fetchall()
        bindings=conn.execute("SELECT generation,observed_state,desired_state,enabled,operation_fence FROM extension_runtime_binding WHERE installation_id=%s",(installation,)).fetchall()
        canary=conn.execute("SELECT count(*) AS n FROM bundle_installation WHERE org_id='dev-org' AND project_id='dev-project'").fetchone()['n']
    observations=[container_observation(row['container_id']) for row in resources]
    alive=[value=='running' for value in observations]
    valid=(len(resources)==3 and all(alive) and canary==0 and len(bindings)==1
        and bindings[0]['observed_state']=='ready' and all(row['generation']==bindings[0]['generation']
        and not row['observed_release'] and row['cleanup_state']=='pending' and row['expires_at']>now for row in resources))
    crossed=now>operation['deadline']
    outcome='CONTINUITY_CROSS_INITIAL_DEADLINE_GREEN' if valid and crossed and len(events)>=3 else 'CONTINUITY_OBSERVING' if valid else 'CONTINUITY_FAILED'
    result=dict(outcome=outcome,installationId=installation,observedAt=now,originalDeadline=operation['deadline'],
        elapsedSeconds=(now-operation['created_at']).total_seconds(),renewalCount=len(events),renewals=events,
        resources=resources,containersRunning=alive,containerObservations=observations,
        bindings=bindings,canaryInstallationCount=canary)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,default=str,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in {'resources','renewals'}},default=str,indent=2))


if __name__=='__main__':main()
