"""Fixed local replacement preparation; never starts or disables a runtime."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT.parent/'.aos-recovery-20260913/state/niushop-1.5-replacement'
INITIAL=STATE/'approved-installation.json'
BUNDLE=ROOT.parent/'.aos-recovery-20260913/state/niushop-1.5-registry/signed-bundles-niushop-1.5'
TRUST=ROOT.parent/'.aos-recovery-20260910/state/a0v-canonical-ecommerce-first-install'
PREDECESSOR=dict(installationId='afd792de-e85e-4680-86d0-c83404824fb3',revision=7,
    lockHash='sha256:539a2b9fc61adab875793153b92c5f7641049bc4dec01c44a6d5fae876c69404',
    overlayRevision='a0v-canonical-ecommerce-v1')
KEY='a0v-niushop-1.5-replacement-20260913-v1'


def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def setup():
    host=load('a0v_ecommerce_runtime_host')
    host._configure_environment(host.DEFAULT_CREDENTIALS,bundle_root=BUNDLE,trust_roots_file=TRUST/'signing/trust-roots.json')
    os.environ['AOS_EXTENSION_RUNTIME_HOST_ENABLED']='0'
    sys.path.insert(0,str(ROOT/'services/aos-api'))
    from aos_api.asset_registry.control_wiring import build_runtime_control_plane
    return build_runtime_control_plane()


def preflight(plane):
    from aos_api.asset_registry.composition_contracts import CurrentInstallationRef
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    scope=dict(org_id='org-org',project_id='dev-project')
    with consumer_connection(runtime_worker_connection,scope) as conn:
        parent=plane.installation_store.load_active_baseline_in_transaction(conn,**scope,
            requested_ref=CurrentInstallationRef.model_validate(PREDECESSOR))
        niushop=[item for item in parent.lock.payload.resolved if item.id=='platform.ecommerce.niushop']
        if len(niushop)!=1 or niushop[0].version!='1.4.0':raise ValueError('exact Niushop1.4 predecessor required')
        binding=conn.execute('''SELECT generation,revision,execution_epoch,enabled,operation_fence,
            desired_state,observed_state FROM extension_runtime_binding
            WHERE org_id=%s AND project_id=%s AND installation_id=%s AND installation_revision=7''',
            (*scope.values(),PREDECESSOR['installationId'])).fetchall()
        if len(binding)!=1:raise ValueError('one predecessor binding required')
        counts=conn.execute("""WITH latest AS (
            SELECT DISTINCT ON(schedule_id) schedule_id,installation_id FROM pipeline_schedule_control_binding
            WHERE org_id=%s AND project_id=%s ORDER BY schedule_id,revision DESC
        ), selected AS (SELECT schedule_id FROM latest WHERE installation_id=%s)
        SELECT
            (SELECT count(*) FROM meta_schedule_run r JOIN selected s ON s.schedule_id=r.schedule_id
                WHERE r.org_id=%s AND r.project_id=%s AND r.executor_stopped IS NOT TRUE) AS unstopped_runs,
            (SELECT count(*) FROM meta_schedule m JOIN selected s ON s.schedule_id=m.id
                WHERE m.org_id=%s AND m.project_id=%s AND m.enabled=true) AS enabled_schedules""",
            (*scope.values(),PREDECESSOR['installationId'],*scope.values(),*scope.values())).fetchone()
        result=dict(outcome='REPLACEMENT_PREDECESSOR_PREFLIGHT_GREEN',observedAt=datetime.now(timezone.utc).isoformat(),
            predecessor=PREDECESSOR,binding=dict(binding[0]),pipelineCounts=dict(counts),installationMutations=0)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--action',choices=('preflight','create'),required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise ValueError('immutable output already exists')
    plane=setup();result=preflight(plane)
    if args.action=='create':
        if INITIAL.exists():raise ValueError('replacement initial receipt exists; observe before further action')
        if result['pipelineCounts']['unstopped_runs']!=0 or result['pipelineCounts']['enabled_schedules']!=0:
            raise ValueError('predecessor schedule activity must be settled first')
        first=load('a0v_canonical_ecommerce_first_install');helper=load('a0v_ecommerce_growth_1_5_registry_successor')
        backup=helper._database_backup(context=helper.DOCKER_CONTEXT,container=helper.DATABASE_CONTAINER,state_dir=STATE)
        connect=first.container_database_connect_factory(context='colima-aos-extension',container='aos-a0v-recovery-pg',database_name='aos_meta_head')
        before=helper._database_counts(connect)
        if before['canary']!=0:raise ValueError('canary installation drift')
        initial=first.create_approved_first_installation(connect_factory=connect,state_dir=TRUST,
            core_version='1.3.0',adapter_version='1.5.0',growth_version='1.7.0',idempotency_prefix=KEY,
            current_installation_ref=PREDECESSOR)
        if initial['installationId']==PREDECESSOR['installationId'] or initial['installationState']!='approved':
            raise ValueError('new approved replacement required')
        after=helper._database_counts(connect)
        if after['canary']!=0 or after['installations']!=before['installations']+1 or after['positive']!=before['positive']+1:
            raise ValueError('unexpected installation count change; observe before further action')
        STATE.mkdir(parents=True,exist_ok=True)
        with INITIAL.open('x') as handle:json.dump(initial,handle,ensure_ascii=False,indent=2);handle.write('\n')
        result.update(outcome='NIUSHOP_1_5_REPLACEMENT_APPROVED',initial=initial,backup=backup,before=before,after=after)
        result['installationMutations']=1+len(initial['transitions'])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,default=str,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,default=str,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
