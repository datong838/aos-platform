"""Fixed, receipt-first local reboot recovery through existing installation Owners."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT.parent/'.aos-recovery-20260913/state/qyh-reboot-recovery'
KEY='a0v-qyh-reboot-recovery-20260913-v1'
PARENT=dict(installationId='eda57424-b8cb-401e-a6f7-94220cb4f9ef',revision=5,
    lockHash='sha256:26e8189ca75d124fe49b27c5e6922a5115071e8f2a7e126c904e3949e4539f59',
    overlayRevision='a0v-canonical-ecommerce-v1')
GENERATION='23afd05b-762c-406a-adfb-247a14412b9f'
SCOPE=dict(org_id='org-org',project_id='dev-project')


def freeze(path,body):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as handle:
        json.dump(body,handle,ensure_ascii=False,default=str,indent=2);handle.write('\n')


def validate_parent(snapshot,*,drained=False):
    head=snapshot['head'];bindings=snapshot['bindings']
    if head['state']!='active' or head['etag_version']!=5 or str(head['installation_id'])!=PARENT['installationId']:
        raise ValueError('current recovery installation differs')
    if len(bindings)!=1:raise ValueError('one predecessor generation required')
    b=bindings[0]
    if (str(b['generation'])!=GENERATION or type(b['revision']) is not int
            or b['revision']!=(7 if drained else 5) or b['execution_epoch']!=(5 if drained else 4)
            or b['enabled'] is not False or b['operation_fence'] is not True
            or b['observed_state']!='unknown'):
        raise ValueError('current recovery binding differs')
    if len(snapshot['resources'])!=3 or any(r['cleanup_state']!='released' or r['observed_release'] is not True for r in snapshot['resources']):
        raise ValueError('predecessor resources are not released')
    if any(o['status'] not in ('succeeded','failed','cancelled') for o in snapshot['operations']):
        raise ValueError('predecessor operation is unresolved')
    if snapshot['businessRoutes']!=0 or any(s['enabled'] is not False or s['unstopped']!=0 for s in snapshot['schedules']):
        raise ValueError('predecessor business activity must settle')


def observe(installation_id):
    from a0v_formal_text_model_renewal import database_connect
    params=(*SCOPE.values(),installation_id)
    with database_connect('aos_meta_head')() as c:
        head=c.execute('''SELECT i.installation_id,i.etag_version,r.state FROM bundle_installation i
            JOIN bundle_installation_revision r ON r.installation_pk=i.installation_pk AND r.org_id=i.org_id
            AND r.project_id=i.project_id AND r.revision=i.current_revision
            WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s''',params).fetchone()
        bindings=c.execute('SELECT generation,revision,execution_epoch,enabled,operation_fence,observed_state,desired_state FROM extension_runtime_binding WHERE org_id=%s AND project_id=%s AND installation_id=%s',params).fetchall()
        resources=c.execute('''SELECT r.cleanup_state,r.observed_release FROM extension_runtime_resource_lease r
            JOIN extension_runtime_operation o USING(org_id,project_id,operation_id)
            WHERE o.org_id=%s AND o.project_id=%s AND o.installation_id=%s''',params).fetchall()
        operations=c.execute('SELECT operation_id,kind,status,phase,revision,failure_code FROM extension_runtime_operation WHERE org_id=%s AND project_id=%s AND installation_id=%s ORDER BY created_at',params).fetchall()
        schedules=c.execute('''WITH latest AS (SELECT DISTINCT ON(schedule_id) schedule_id,installation_id
            FROM pipeline_schedule_control_binding WHERE org_id=%s AND project_id=%s ORDER BY schedule_id,revision DESC)
            SELECT m.id,m.enabled,(SELECT count(*) FROM meta_schedule_run r WHERE r.org_id=m.org_id AND r.project_id=m.project_id
            AND r.schedule_id=m.id AND r.executor_stopped IS NOT TRUE) AS unstopped FROM latest l JOIN meta_schedule m ON m.id=l.schedule_id
            WHERE l.installation_id=%s AND m.org_id=%s AND m.project_id=%s''',(*params,*SCOPE.values())).fetchall()
        routes=c.execute('SELECT count(*) AS n FROM extension_operation_dispatch_binding WHERE org_id=%s AND project_id=%s',tuple(SCOPE.values())).fetchone()['n']
    return dict(at=datetime.now(timezone.utc).isoformat(),head=head,bindings=bindings,resources=resources,operations=operations,schedules=schedules,businessRoutes=routes)


def run(action):
    import a0v_niushop_1_5_replacement as prior
    plane=prior.setup()
    initial=STATE/'create-result.json'
    if action=='observe':
        result={'parent':observe(PARENT['installationId'])}
        if initial.exists():result['candidate']=observe(json.loads(initial.read_text())['installationId'])
        return result
    parent=observe(PARENT['installationId'])
    validate_parent(parent,drained=action!='disable')
    activation=prior.load('a0v_ecommerce_growth_1_4_activate')
    if action=='disable':
        command=dict(installationId=PARENT['installationId'],etag=5,target=dict(generation=GENERATION,bindingRevision=5))
        freeze(STATE/'disable-intent.json',command)
        result=plane.disable_service.request(**SCOPE,installation_id=command['installationId'],actor=activation.ACTOR,
            roles=activation.ROLES,markings=activation.MARKINGS,idempotency_key=KEY+'-disable',if_match='"5"',target=command['target']).response_json
    elif action=='create':
        from aos_api.extension_runtime.consumer_connection import consumer_connection
        from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
        from aos_api.extension_runtime.replacement_enable_guard import require_predecessor_drained
        from aos_api.asset_registry.composition_contracts import CurrentInstallationRef
        with consumer_connection(runtime_worker_connection,SCOPE) as conn:
            require_predecessor_drained(conn,**SCOPE,requested_ref=CurrentInstallationRef.model_validate(PARENT))
        first=prior.load('a0v_canonical_ecommerce_first_install');helper=prior.load('a0v_ecommerce_growth_1_5_registry_successor')
        if (STATE/'create-intent.json').exists():raise ValueError('creation intent exists; observe without resending')
        backup=helper._database_backup(context=helper.DOCKER_CONTEXT,container=helper.DATABASE_CONTAINER,state_dir=STATE)
        freeze(STATE/'create-intent.json',dict(predecessor=PARENT,backup=backup,key=KEY))
        connect=first.container_database_connect_factory(context='colima-aos-extension',container='aos-a0v-recovery-pg',database_name='aos_meta_head')
        result=first.create_approved_first_installation(connect_factory=connect,state_dir=prior.TRUST,
            core_version='1.3.0',adapter_version='1.5.0',growth_version='1.7.0',idempotency_prefix=KEY,current_installation_ref=PARENT)
    else:
        candidate=json.loads(initial.read_text())['installationId'];current=observe(candidate)
        expected=('approved',3,'runtime-apply') if action=='prepare' else ('applied',4,'runtime-verify')
        if (current['head']['state'],current['head']['etag_version'])!=expected[:2] or current['bindings']:
            raise ValueError('candidate phase differs')
        freeze(STATE/(action+'-intent.json'),dict(installationId=candidate,etag=expected[1],kind=expected[2]))
        result=plane.lifecycle_service.request_preparation(**SCOPE,installation_id=candidate,actor=activation.ACTOR,
            roles=activation.ROLES,markings=activation.MARKINGS,idempotency_key=KEY+'-'+action,
            if_match='"'+str(expected[1])+'"',kind=expected[2]).response_json
    freeze(STATE/(action+'-result.json'),result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('observe','disable','create','prepare','verify'))
    args=parser.parse_args()
    print(json.dumps(run(args.action),default=str,ensure_ascii=False,indent=2))
