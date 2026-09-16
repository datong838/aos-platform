"""Group configuration CAS and stop behavior with original PG controls."""
import hashlib
import json
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
from aos_api.pipeline_snapshot_schedule_definition import PipelineSnapshotScheduleDefinitionOwner
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
    selections._artifacts=NS(scope=args['scope'],load_record=lambda *a:NS(manifest=NS(spec=NS(exports=NS(policies=['content/policies/'])))),read_artifact=lambda *a:raw)
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
