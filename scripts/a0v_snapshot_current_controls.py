"""Bounded current twelve-source approvals; no source reader or group enable."""
from datetime import timedelta
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT.parent/'.aos-recovery-20260916/state/snapshot-current-controls'
INSTALLATION='d6531562-e388-4206-a3ba-a89aaddc255c'
GENERATION='5295b81e-6005-4c2e-befc-3323f1456b8c'
ACTOR='a0v-ecommerce-growth-1.4-runtime-owner'


def wire(value):
    return value.model_dump(mode='json',by_alias=True) if value is not None else None


def confirm_once(path, request, *, submit, read):
    """A frozen intent permits one submission; later calls only read its receipt."""
    from a0v_qyh_current_product_event_first_chain import freeze_or_match
    existed=path.exists()
    if existed:freeze_or_match(path,request)
    actual=read()
    if actual is not None:
        freeze_or_match(path,request)
        return actual
    if existed:raise ValueError('original approval unconfirmed; no resend')
    freeze_or_match(path,request)
    try:submit()
    except Exception:pass
    actual=read()
    if actual is None:raise ValueError('original approval unconfirmed; no resend')
    return actual


def preflight():
    from psycopg import Rollback
    from a0v_ecommerce_runtime_host import _configure_environment,DEFAULT_CREDENTIALS
    from a0v_event_complete_product_api import BUNDLE_ROOT
    from a0v_p02_current_preflight import TRUST_ROOTS
    _configure_environment(DEFAULT_CREDENTIALS,bundle_root=BUNDLE_ROOT,trust_roots_file=TRUST_ROOTS)
    os.environ['AOS_EXTENSION_RUNTIME_HOST_ENABLED']='0'
    from aos_api.asset_registry.control_wiring import build_runtime_control_plane
    from aos_api.asset_registry.composition_contracts import CurrentInstallationRef
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.tenant_scope import TenantScope
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    from aos_api.source_configuration_revision import SourceConfigurationRevisionStore
    from aos_api.pipeline_runtime_control_contracts import PipelineSourceSelectionDraft
    from aos_api.pipeline_source_selection_store import decode_selection_row
    from aos_api.pipeline_runtime_control_owner import decode_control_row
    from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner
    from aos_api.ec_ingress_journal import _digest
    from a0v_snapshot_configuration_preview import build_preview
    from aos_api.asset_registry.canonical_json import canonical_sha256
    scope=TenantScope('org-org','dev-project');plane=build_runtime_control_plane()
    service=plane.pipeline_control_factory.build(scope)
    with consumer_connection(runtime_worker_connection,dict(org_id=scope.org_id,project_id=scope.project_id)) as c:
        head=c.execute('''SELECT i.current_revision,r.state,r.lock_hash,r.overlay_revision FROM bundle_installation i
            JOIN bundle_installation_revision r ON (i.org_id,i.project_id,i.installation_pk,i.current_revision)=
            (r.org_id,r.project_id,r.installation_pk,r.revision) WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s''',(*scope.key,INSTALLATION)).fetchone()
        if not head or head['state']!='active' or head['current_revision']!=5:raise ValueError('current J differs')
        ref=CurrentInstallationRef.model_validate(dict(installationId=INSTALLATION,revision=5,lockHash=head['lock_hash'],overlayRevision=head['overlay_revision']))
        baseline=plane.installation_store.load_active_baseline_in_transaction(c,org_id=scope.org_id,project_id=scope.project_id,requested_ref=ref)
        selected,=[x for x in baseline.lock.payload.resolved if x.id=='platform.ecommerce.niushop']
        preview=build_preview(service.selections._artifacts,selected,'niushop-qyh')
        binding=c.execute('SELECT * FROM extension_runtime_binding WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s',(*scope.key,INSTALLATION,GENERATION)).fetchone()
        if not binding or not binding['enabled'] or binding['operation_fence'] or binding['execution_epoch']!=3 or binding['revision']!=6:raise ValueError('current J binding differs')
        source=SourceConfigurationRevisionStore(HostTransaction(c),scope).read_current('niushop-qyh')
        now=c.execute('SELECT clock_timestamp() AS now').fetchone()['now'];members=[]
        for member in preview['members']:
            pipeline=member['pipelineId']
            graph=c.execute('SELECT revision,payload FROM phase5_pipeline_graph WHERE org_id=%s AND project_id=%s AND pipeline_id=%s',(*scope.key,pipeline)).fetchone()
            schedules=c.execute('SELECT id,enabled,ingest FROM meta_schedule WHERE org_id=%s AND project_id=%s AND pipeline_id=%s',(*scope.key,pipeline)).fetchall()
            if len(schedules)!=1 or schedules[0]['enabled'] is not False:raise ValueError('one disabled schedule per pipeline required')
            schedule=schedules[0]
            draft=PipelineSourceSelectionDraft.model_validate(dict(orgId=scope.org_id,projectId=scope.project_id,
                pipelineId=pipeline,graphRevision=graph['revision'],graphHash=_digest(graph['payload']),installationRef=wire(ref),
                generation=GENERATION,executionEpoch=3,configurationRef=binding['config_ref'],
                packageRef=dict(publisher=selected.publisher,id=selected.id,version=selected.version,contentHash=selected.content_hash),
                sourceId='niushop-qyh',sourceConfigurationRef=wire(source.ref),rowLimit=1000,timeoutSeconds=30,maxSourceCalls=1,
                notBefore=now,expiresAt=now+timedelta(hours=4),**member['artifactRefs']))
            service.selections._guarded(c,draft,ACTOR,lambda value:True,snapshot=True)
            previous={}
            for name,table,decode in [('selection','pipeline_source_selection_revision',decode_selection_row),('control','pipeline_runtime_control_revision',decode_control_row)]:
                rows=c.execute(f'SELECT * FROM {table} WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s AND pipeline_id=%s ORDER BY revision DESC LIMIT 1',(*scope.key,INSTALLATION,GENERATION,pipeline)).fetchall()
                previous[name]=wire(decode(rows[0]).ref) if rows else None
            old_binding=PipelineScheduleControlOwner.read_latest(c,scope=scope,schedule_id=schedule['id'])
            previous['binding']=wire(old_binding.ref) if old_binding else None
            members.append(dict(pipelineId=pipeline,scheduleId=schedule['id'],draft=wire(draft),previous=previous))
        path='content/policies/snapshot-relationships.v1.json'
        raw=service.selections._artifacts.read_artifact(selected,path,256*1024)
        import hashlib
        policy=dict(resourceType='SnapshotRelationshipPolicy',resourceId=path,revision=selected.version,contentHash='sha256:'+hashlib.sha256(raw).hexdigest())
        result=dict(actor=ACTOR,installationRef=wire(ref),generation=GENERATION,preparedAt=now.isoformat(),
            policyRef=policy,members=members,sourceReads=0,enabled=False)
        result['previewHash']=canonical_sha256(result)
        raise Rollback()
    return result


if __name__=='__main__':
    from a0v_qyh_current_product_event_first_chain import freeze_or_match
    result=preflight()
    freeze_or_match(STATE/'preflight.json',result)
    print(json.dumps(dict(outcome='CURRENT_TWELVE_SOURCE_PREFLIGHT',members=len(result['members']),actor=ACTOR,sourceReads=0)))
