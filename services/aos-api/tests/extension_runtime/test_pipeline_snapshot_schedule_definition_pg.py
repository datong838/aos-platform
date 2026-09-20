"""Group configuration CAS and stop behavior with original PG controls."""
import hashlib
import json
from dataclasses import replace
from types import SimpleNamespace as NS
from uuid import uuid4

import pytest

from test_pipeline_snapshot_schedule_claim_pg import schedule_group
from test_analysis_snapshot_native_claims_pg import (
    native_claims_case,host_case,control_governed,governed,service_case,stored,pair,body,
)
from tests.asset_registry.test_installation_store import _composition_inputs
from aos_api.asset_registry.composition_store import PostgresCompositionStore
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_snapshot_schedule_definition import PipelineSnapshotScheduleDefinitionOwner, _reference
from aos_api.source_readiness_contracts import CANONICAL_QYH_SOURCES


def complete_configuration_installation(conn, scope, actor):
    """Persist a model-valid original lock; named assets remain fixture-only."""
    conn.execute('RESET ROLE')
    request, snapshot, payload = _composition_inputs()
    lock = PostgresCompositionStore().create_or_get_in_transaction(conn,
        org_id=scope.org_id, project_id=scope.project_id, request=request,
        snapshot=snapshot, payload=payload, created_by='fixture')
    composition = conn.execute('SELECT composition_pk FROM bundle_composition WHERE composition_id=%s',
        (lock.composition_id,)).fetchone()['composition_pk']
    installation = conn.execute('SELECT installation_pk FROM bundle_installation').fetchone()['installation_pk']
    conn.execute("""INSERT INTO bundle_installation_revision(org_id,project_id,installation_pk,revision,
        state,composition_pk,lock_revision,lock_hash,permission_diff_hash,migration_plan_hash,
        contribution_diff_hash,overlay_revision,requested_by)
        VALUES(%s,%s,%s,1,'draft',%s,1,%s,%s,%s,%s,'configuration-test-draft','fixture')""",
        (*scope.key,installation,composition,lock.lock_hash,lock.permission_diff_hash,
         lock.migration_plan_hash,lock.contribution_diff_hash))
    conn.execute("""INSERT INTO bundle_installation_event(org_id,project_id,installation_pk,sequence,
        from_revision,to_revision,from_state,to_state,actor)
        VALUES(%s,%s,%s,1,NULL,1,NULL,'draft','fixture')""", (*scope.key,installation))
    conn.execute("""INSERT INTO meta_membership(org_id,project_id,subject,role)
        VALUES(%s,%s,%s,'admin') ON CONFLICT (org_id,project_id,subject) DO UPDATE SET role='admin'""",
        (*scope.key,actor))
    conn.execute('SET CONSTRAINTS ALL IMMEDIATE')


@pytest.fixture
def definition_case(schedule_group):
    conn, claim, args = schedule_group
    current = claim._groups.run_current(conn,scope=args['scope'],actor=args['actor'],
        refs=tuple(b.control_ref for b in args['bindings']),execute=lambda g:g)
    package = current.members[0][1].package_ref
    raw = json.dumps(dict(schemaVersion='aos.snapshot-relationships/v1',
        objectTypes=[s.object_type for s in CANONICAL_QYH_SOURCES],
        rules=[dict(linkType='Shop.hasWeapp',rowType='Weapp',parentType='Shop',
            referenceProperty='siteId',direction='parent-to-row',encoding='positive-id',allowUnset=False)])).encode()
    selected=NS(publisher=package.publisher,id=package.id,version=package.version,content_hash=package.content_hash,
        signature_fingerprint='named-signature',release_evidence_revision=1)
    selections=claim._groups._controls._selections
    selections._store=NS(load_active_baseline_in_transaction=lambda *a,**k:NS(lock=NS(payload=NS(resolved=[selected]))))
    selections._artifacts=NS(scope=args['scope'],load_record=lambda *a:NS(manifest=NS(spec=NS(exports=NS(policies=['content/policies/']))),artifacts=[dict(relativePath='content/policies/native.json',digest='sha256:'+hashlib.sha256(raw).hexdigest(),size=len(raw),mediaType='application/json')]),read_artifact=lambda *a:raw)
    selections._release_policy=NS(evaluate=lambda *a,**k:None)
    complete_configuration_installation(conn,args['scope'],args['actor'])
    conn.execute('SET LOCAL ROLE aos_runtime')
    owner=PipelineSnapshotScheduleDefinitionOwner(controls=claim._groups._controls,installation_store=PostgresInstallationStore())
    policy=PipelineExactRef(resourceType='SnapshotRelationshipPolicy',resourceId='content/policies/native.json',
        revision=package.version,contentHash='sha256:'+hashlib.sha256(raw).hexdigest())
    command=dict(scope=args['scope'],definition_id=str(uuid4()),actor=args['actor'],
        cron='0 8 * * *',policy_ref=policy,bindings=args['bindings'],expected_ref=None,idempotency_key='configure')
    return conn,owner,command


def test_configure_enable_disable_retire_keeps_history(definition_case):
    conn,owner,args=definition_case
    first=owner.configure(conn,**args)
    assert first['body']['state']=='disabled'
    assert owner.configure(conn,**args)==first
    conn.execute('SET CONSTRAINTS snapshot_definition_revision_complete,snapshot_definition_head_complete,snapshot_definition_member_complete IMMEDIATE')
    assert conn.execute('SELECT count(*) AS n FROM meta_schedule WHERE enabled').fetchone()['n']==0
    common={k:args[k] for k in ('scope','definition_id','actor')}
    enabled=owner.transition(conn,**common,intent='enable',expected_ref=first['ref'],idempotency_key='enable')
    assert enabled['body']['state']=='enabled'
    assert conn.execute('SELECT count(*) AS n FROM meta_schedule WHERE enabled').fetchone()['n']==12
    disabled=owner.transition(conn,**common,intent='disable',expected_ref=enabled['ref'],idempotency_key='disable')
    assert disabled['body']['state']=='disabled'
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_schedule_current_member').fetchone()['n']==12
    retired=owner.transition(conn,**common,intent='retire',expected_ref=disabled['ref'],idempotency_key='retire')
    assert retired['body']['state']=='retired'
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_schedule_current_member').fetchone()['n']==0
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_schedule_definition_revision').fetchone()['n']==4
    assert owner.transition(conn,**common,intent='enable',expected_ref=first['ref'],idempotency_key='enable')==enabled
    assert owner.read(conn,scope=args['scope'],definition_id=args['definition_id'])==retired


def test_disabled_definition_can_retire_after_formal_installation_release(definition_case,monkeypatch):
    conn,owner,args=definition_case
    first=owner.configure(conn,**args)
    monkeypatch.setattr(owner,'_released_retirement_allowed',lambda *a,**k:True)
    monkeypatch.setattr(owner,'_permission',lambda *a,**k:(_ for _ in ()).throw(AssertionError('released path reopened permission')))
    retired=owner.transition(conn,scope=args['scope'],definition_id=args['definition_id'],actor=args['actor'],
        intent='retire',expected_ref=first['ref'],idempotency_key='released-retire')
    assert retired['body']['state']=='retired'
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_schedule_current_member').fetchone()['n']==0


def test_released_retirement_never_bypasses_non_retire_permission(definition_case,monkeypatch):
    conn,owner,args=definition_case
    first=owner.configure(conn,**args)
    monkeypatch.setattr(owner,'_released_retirement_allowed',lambda *a,**k:True)
    monkeypatch.setattr(owner,'_permission',lambda *a,**k:False)
    with pytest.raises(PermissionError,match='current installation'):
        owner.transition(conn,scope=args['scope'],definition_id=args['definition_id'],actor=args['actor'],
            intent='enable',expected_ref=first['ref'],idempotency_key='released-cannot-enable')


def test_membership_and_revision_conflicts_do_not_change_configuration(definition_case):
    conn,owner,args=definition_case
    first=owner.configure(conn,**args)
    with pytest.raises(ValueError),conn.transaction():
        owner.configure(conn,**(args|{'definition_id':str(uuid4()),'idempotency_key':'second'}))
    with pytest.raises(ValueError),conn.transaction():
        owner.configure(conn,**(args|{'idempotency_key':'stale'}))
    assert owner.read(conn,scope=args['scope'],definition_id=args['definition_id'])==first
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_schedule_definition_head').fetchone()['n']==1


@pytest.mark.parametrize('fault',['revoked','viewer','other-actor'])
def test_current_configuration_permission_is_required(definition_case,fault):
    conn,owner,args=definition_case
    first=owner.configure(conn,**args)
    conn.execute('RESET ROLE')
    if fault=='revoked':
        conn.execute('DELETE FROM meta_membership WHERE subject=%s',(args['actor'],))
    elif fault=='viewer':
        conn.execute("UPDATE meta_membership SET role='viewer' WHERE subject=%s",(args['actor'],))
    conn.execute('SET LOCAL ROLE aos_runtime')
    from aos_api.asset_registry.errors import AssetRegistryError
    from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
    with pytest.raises((PermissionError,AssetRegistryError,RuntimeConflict)),conn.transaction():
        owner.transition(conn,scope=args['scope'],definition_id=args['definition_id'],
            actor='unassigned' if fault=='other-actor' else args['actor'],intent='enable',
            expected_ref=first['ref'],idempotency_key='denied')
    assert owner.read(conn,scope=args['scope'],definition_id=args['definition_id'])==first


def test_disable_does_not_reopen_denied_source_and_preserves_executor(definition_case):
    conn,owner,args=definition_case
    first=owner.configure(conn,**args)
    common={k:args[k] for k in ('scope','definition_id','actor')}
    enabled=owner.transition(conn,**common,intent='enable',expected_ref=first['ref'],idempotency_key='enable')
    def source_denied(*a,**kw):
        raise PermissionError('named expired source authority')
    owner._groups._groups._controls._selections._guarded=source_denied
    conn.execute('RESET ROLE')
    conn.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,'stop-admin','admin')",args['scope'].key)
    conn.execute('SET LOCAL ROLE aos_runtime')
    disabled=owner.transition(conn,**(common|{'actor':'stop-admin'}),intent='disable',
        expected_ref=enabled['ref'],idempotency_key='stop')
    assert disabled['body']['actor']=='stop-admin'
    assert disabled['body']['executor']==args['actor']
    assert conn.execute('SELECT count(*) AS n FROM meta_schedule WHERE enabled').fetchone()['n']==0
    with pytest.raises(PermissionError,match='expired source'),conn.transaction():
        owner.transition(conn,**common,intent='enable',expected_ref=disabled['ref'],idempotency_key='reopen')
    assert owner.read(conn,scope=args['scope'],definition_id=args['definition_id'])==disabled


@pytest.mark.parametrize('status,stopped',[('running',True),('failed',False)])
@pytest.mark.parametrize('intent',['configure','retire'])
def test_active_or_unknown_runs_block_reconfiguration_and_retirement(definition_case,status,stopped,intent):
    conn,owner,args=definition_case
    first=owner.configure(conn,**args)
    conn.execute("""INSERT INTO meta_schedule_run(id,org_id,project_id,schedule_id,scheduled_for,trigger,status,executor_stopped)
        VALUES('pending-member',%s,%s,%s,date_trunc('minute',clock_timestamp()),'manual',%s,%s)""",
        (*args['scope'].key,args['bindings'][-1].schedule_id,status,stopped))
    with pytest.raises(ValueError,match='active or unknown'),conn.transaction():
        if intent=='configure':
            owner.configure(conn,**(args|{'expected_ref':first['ref'],'idempotency_key':'edit'}))
        else:
            owner.transition(conn,**{k:args[k] for k in ('scope','definition_id','actor')},intent=intent,
                expected_ref=first['ref'],idempotency_key='retire')
    assert owner.read(conn,scope=args['scope'],definition_id=args['definition_id'])==first
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_schedule_current_member').fetchone()['n']==12


def test_tenant_isolation_and_immutable_history(definition_case):
    import psycopg
    from aos_api.tenant_scope import TenantScope
    conn,owner,args=definition_case
    owner.configure(conn,**args)
    for sql in ('UPDATE pipeline_snapshot_schedule_definition_revision SET actor=actor',
                'DELETE FROM pipeline_snapshot_schedule_definition_member',
                'DELETE FROM pipeline_snapshot_schedule_definition_head',
                'TRUNCATE pipeline_snapshot_schedule_current_member'):
        with pytest.raises(psycopg.Error),conn.transaction():conn.execute(sql)
    conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
    assert owner.read(conn,scope=TenantScope('dev-org','dev-project'),definition_id=args['definition_id']) is None
    for table in ('pipeline_snapshot_schedule_definition_revision','pipeline_snapshot_schedule_definition_member',
                  'pipeline_snapshot_schedule_definition_head','pipeline_snapshot_schedule_current_member'):
        assert conn.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n']==0


@pytest.mark.parametrize('cron',['0-999999999 8 * * *','0,99 8 * * *','*/0 8 * * *','5-1 8 * * *','0  8 * * *'])
def test_invalid_cron_is_rejected_before_database_access(cron):
    from aos_api.pipeline_snapshot_schedule_definition import _cron
    with pytest.raises(ValueError):_cron(cron)


def test_edit_disabled_definition_creates_exact_successor(definition_case):
    conn,owner,args=definition_case
    first=owner.configure(conn,**args)
    edited=owner.configure(conn,**(args|{'cron':'*/15 9 * * *','expected_ref':first['ref'],'idempotency_key':'edit'}))
    assert edited['body']['revision']==2
    assert edited['body']['priorRef']==first['ref']
    assert edited['body']['cron']=='*/15 9 * * *'
    assert edited['body']['state']=='disabled'
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_schedule_current_member WHERE revision=2').fetchone()['n']==12


def test_ordinary_configure_cannot_transfer_installation(definition_case,monkeypatch):
    conn,owner,args=definition_case
    first=owner.configure(conn,**args)
    target_installation,target_generation=str(uuid4()),str(uuid4())
    transferred=tuple(replace(binding,installation_id=target_installation,generation=target_generation)
                      for binding in args['bindings'])
    monkeypatch.setattr(owner,'_permission',lambda *a,**k:True)
    with pytest.raises(ValueError,match='cannot transfer'),conn.transaction():
        owner.configure(conn,**(args|{'bindings':transferred,'expected_ref':first['ref'],
            'idempotency_key':'ordinary-transfer-denied'}))
    assert owner.read(conn,scope=args['scope'],definition_id=args['definition_id'])==first


def test_saved_recovery_transfer_uses_dedicated_gate(definition_case,monkeypatch):
    conn,owner,args=definition_case
    first=owner.configure(conn,**args)
    target_installation,target_generation=str(uuid4()),str(uuid4())
    transferred=tuple(replace(binding,installation_id=target_installation,generation=target_generation)
                      for binding in args['bindings'])
    monkeypatch.setattr(owner,'_permission',lambda *a,**k:True)
    def blocked(*_args,**_kwargs):
        raise ValueError('saved recovery gate reached')
    monkeypatch.setattr(owner,'_require_saved_recovery_transfer',blocked)
    with pytest.raises(ValueError,match='gate reached'),conn.transaction():
        owner.transfer_saved_recovery(conn,scope=args['scope'],definition_id=args['definition_id'],
            group_id=str(uuid4()),actor=args['actor'],bindings=transferred,expected_ref=first['ref'],
            expected_recovery_ref={'resourceType':'SnapshotGroupRecoveryRevision',
                'resourceId':'snapshot-recovery-'+str(uuid4()),'revision':1,
                'contentHash':'sha256:'+'a'*64},idempotency_key='dedicated-transfer')
    assert owner.read(conn,scope=args['scope'],definition_id=args['definition_id'])==first


def test_saved_recovery_resolves_same_policy_path_from_target_release():
    old=PipelineExactRef(resourceType='SnapshotRelationshipPolicy',
        resourceId='content/policies/native.json',revision='1.0.0',contentHash='sha256:'+'1'*64)
    new=old.model_copy(update={'revision':'2.0.0','content_hash':'sha256:'+'2'*64})
    control_ref=PipelineExactRef(resourceType='PipelineRuntimeControlRevision',
        resourceId='pipeline-control-'+str(uuid4()),revision=1,contentHash='sha256:'+'3'*64)
    binding=NS(control_ref=control_ref,actor='owner')
    current_group=object()

    class CurrentGroups:
        def run_current(self,_conn,**kwargs):
            assert kwargs['refs']==(control_ref,)
            assert kwargs['actor']=='owner'
            return kwargs['execute'](current_group)

    class Policies:
        _groups=CurrentGroups()
        def _resolve_exported_ref(self,_conn,scope,group,*,resource_type,path):
            assert scope.key==('org-org','dev-project')
            assert group is current_group
            assert resource_type=='SnapshotRelationshipPolicy'
            assert path==old.resource_id
            return new

    owner=object.__new__(PipelineSnapshotScheduleDefinitionOwner)
    owner._groups=Policies()
    result=owner._current_transfer_policy(object(),scope=NS(key=('org-org','dev-project')),
        bindings=(binding,),prior={'policyRef':old.model_dump(mode='json',by_alias=True)})
    assert result==new


def test_saved_recovery_accepts_only_exact_finite_active_replacement_chain():
    scope=NS(key=('org-org','dev-project'))
    old,intermediate,new=(str(uuid4()) for _ in range(3))

    def ref(installation,revision):
        return {'installationId':installation,'revision':revision,
            'lockHash':f'sha256:{revision:064x}','overlayRevision':'overlay-v1'}

    rows={
        old:{'current_revision':5,'state':'active','lock_hash':ref(old,5)['lockHash'],
            'overlay_revision':'overlay-v1','lock_payload':{'currentInstallationRef':None}},
        intermediate:{'current_revision':5,'state':'active','lock_hash':ref(intermediate,5)['lockHash'],
            'overlay_revision':'overlay-v1','lock_payload':{'currentInstallationRef':ref(old,5)}},
        new:{'current_revision':5,'state':'active','lock_hash':ref(new,5)['lockHash'],
            'overlay_revision':'overlay-v1','lock_payload':{'currentInstallationRef':ref(intermediate,5)}},
    }

    class Connection:
        def execute(self,_sql,args):
            return NS(fetchone=lambda:rows.get(args[-1]))

    method=PipelineSnapshotScheduleDefinitionOwner._exact_active_replacement_lineage
    assert method(Connection(),scope=scope,old_installation=old,new_installation=new)==[
        old,intermediate,new]
    rows[new]['lock_payload']['currentInstallationRef']=ref(old,5)
    assert method(Connection(),scope=scope,old_installation=old,new_installation=new)==[old,new]

    rows[new]['lock_payload']['currentInstallationRef']=ref(intermediate,4)
    with pytest.raises(ValueError,match='exact active replacement lineage'):
        method(Connection(),scope=scope,old_installation=old,new_installation=new)
    rows[new]['lock_payload']['currentInstallationRef']=ref(intermediate,5)
    rows[intermediate]['state']='disabled'
    with pytest.raises(ValueError,match='exact active replacement lineage'):
        method(Connection(),scope=scope,old_installation=old,new_installation=new)
    rows[intermediate]['state']='active'
    rows[intermediate]['lock_payload']['currentInstallationRef']=ref(new,5)
    with pytest.raises(ValueError,match='exact active replacement lineage'):
        method(Connection(),scope=scope,old_installation=old,new_installation=new)


def test_saved_recovery_anchor_allows_only_an_exact_chained_transfer():
    from aos_api.asset_registry.canonical_json import canonical_sha256
    from aos_api.tenant_scope import TenantScope

    scope=TenantScope('org-org','dev-project')
    definition_id=str(uuid4())
    recovery_ref={'resourceType':'SnapshotGroupRecoveryRevision','resourceId':'snapshot-recovery-group-a',
        'revision':1,'contentHash':'sha256:'+'7'*64}
    anchor_hash='sha256:'+'3'*64
    def body(revision,prior,installation):
        return {'schemaVersion':'aos.snapshot-schedule-definition/v1','orgId':scope.org_id,
            'projectId':scope.project_id,'definitionId':definition_id,'revision':revision,
            'priorRef':prior,'installationId':installation,'generation':str(uuid4()),'state':'disabled',
            'cron':'0 8 * * *','timezone':'Asia/Shanghai','policyRef':{},'members':[{} for _ in range(12)],
            'executor':'owner','actor':'owner','createdAt':'2026-09-17T00:00:00+00:00'}
    ref3={'resourceType':'SnapshotScheduleDefinitionRevision','resourceId':'snapshot-schedule-'+definition_id,
        'revision':3,'contentHash':anchor_hash}
    previous=body(4,ref3,str(uuid4()))
    ref4=_reference(previous)
    current=body(5,ref4,str(uuid4()))
    request5={'orgId':scope.org_id,'projectId':scope.project_id,'definitionId':definition_id,
        'actor':'owner','intent':'transfer_saved_recovery','expectedRef':ref4,'settings':None,
        'transfer':{'groupId':'group-a','expectedRecoveryRef':recovery_ref}}
    rows={
        (5,None):{'body':current,'content_hash':_reference(current)['contentHash'],'revision':5,
            'state':'disabled','request':request5,'request_hash':canonical_sha256(request5)},
        (4,ref4['contentHash']):{'body':previous,'content_hash':ref4['contentHash'],'revision':4,
            'state':'disabled','request':{},'request_hash':canonical_sha256({})},
    }
    class Connection:
        def execute(self,_sql,args):
            revision=args[-1] if len(args)==4 else args[-2]
            content_hash=None if len(args)==4 else args[-1]
            return NS(fetchone=lambda:rows.get((revision,content_hash)))
    assert PipelineSnapshotScheduleDefinitionOwner._saved_recovery_anchor(Connection(),scope=scope,
        prior=current,group_id='group-a',recovery_ref=recovery_ref,
        recovery_revision=3,recovery_hash=anchor_hash) is True
    assert PipelineSnapshotScheduleDefinitionOwner._saved_recovery_anchor(Connection(),scope=scope,
        prior=current,group_id='group-b',recovery_ref=recovery_ref,
        recovery_revision=3,recovery_hash=anchor_hash) is False
