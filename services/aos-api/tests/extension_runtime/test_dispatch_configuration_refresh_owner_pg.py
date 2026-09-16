"""Atomic refresh on disposable PostgreSQL; fixtures are not live approval."""
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from uuid import UUID,uuid4

import psycopg
from psycopg.types.json import Jsonb
import pytest

pytest_plugins=('test_product_event_control_host_service',)

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_dispatch_configuration_receipt import decode_receipt
from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
from aos_api.ecommerce_growth_lifecycle import EcommerceGrowthDisableDependent
from aos_api.extension_runtime.binding_store import RuntimeBindingStore
from aos_api.extension_runtime.lifecycle_store import RuntimeOperationStore
from aos_api.tenant_scope import TenantScope
from test_dispatch_configuration_refresh_schema_pg import ledger


def seed_operation(conn, saved, *, kind, operation_id, revision, binding_revision):
    req=saved['request'];installation=UUID(req['installationRef']['installationId'])
    target=dict(generation=req['generation'],bindingRevision=binding_revision,
        configRef=deepcopy(req['targetConfigurationRef']))
    conn.execute('''INSERT INTO extension_runtime_operation(org_id,project_id,operation_id,
        installation_id,kind,idempotency_key,request_hash,requested_by,expected_installation_etag,
        expected_binding_revision,status,phase,revision,deadline)
        VALUES(%s,%s,%s,%s,%s,%s,%s,'fixture-admin',%s,%s,'succeeded','succeeded',%s,%s)''',
        (saved['org_id'],saved['project_id'],operation_id,installation,kind,
         'refresh-'+kind+'-'+str(operation_id),
         'sha256:'+'b'*64,saved['_etag'],binding_revision,revision,
         datetime.now(timezone.utc)+timedelta(hours=1)))
    payload={'kind':kind,'configurationTarget':target}
    conn.execute('''INSERT INTO extension_runtime_event(org_id,project_id,operation_id,sequence,
        event_id,type,payload,payload_hash) VALUES(%s,%s,%s,1,%s,'accepted',%s,%s)''',
        (saved['org_id'],saved['project_id'],operation_id,uuid4(),Jsonb(payload),canonical_sha256(payload)))


@pytest.fixture
def owner_case(ledger):
    conn,saved=ledger;req=saved['request']
    installation_pk=conn.execute('SELECT installation_pk FROM bundle_installation WHERE org_id=%s '
        'AND project_id=%s AND installation_id=%s',(saved['org_id'],saved['project_id'],
        saved['installation_id'])).fetchone()['installation_pk']
    # Structural current-installation parent for this isolated Owner test. Foreign
    # key triggers are disabled only around this synthetic parent insertion.
    conn.execute('ALTER TABLE bundle_installation_revision DISABLE TRIGGER ALL')
    conn.execute('''INSERT INTO bundle_installation_revision(org_id,project_id,installation_pk,revision,
        state,composition_pk,lock_revision,lock_hash,permission_diff_hash,migration_plan_hash,
        contribution_diff_hash,overlay_revision,requested_by)
        VALUES(%s,%s,%s,1,'draft',%s,1,%s,%s,%s,%s,'tenant-overlay','fixture-admin')''',
        (saved['org_id'],saved['project_id'],installation_pk,uuid4(),req['installationRef']['lockHash'],
         'sha256:'+'1'*64,'sha256:'+'2'*64,'sha256:'+'3'*64))
    conn.execute('ALTER TABLE bundle_installation_revision ENABLE TRIGGER ALL')
    conn.execute('ALTER TABLE bundle_installation_event DISABLE TRIGGER ALL')
    conn.execute('''INSERT INTO bundle_installation_event(org_id,project_id,installation_pk,sequence,
        from_revision,to_revision,from_state,to_state,actor)
        VALUES(%s,%s,%s,1,NULL,1,NULL,'draft','fixture-admin')''',
        (saved['org_id'],saved['project_id'],installation_pk))
    conn.execute('ALTER TABLE bundle_installation_event ENABLE TRIGGER ALL')
    conn.commit()
    conn.execute('ALTER TABLE bundle_installation DISABLE TRIGGER ALL')
    conn.execute('UPDATE bundle_installation SET active_revision=1 WHERE org_id=%s AND project_id=%s '
        'AND installation_id=%s',(saved['org_id'],saved['project_id'],saved['installation_id']))
    conn.execute('ALTER TABLE bundle_installation ENABLE TRIGGER ALL')
    installation=conn.execute('''SELECT i.installation_pk,i.current_revision,i.active_revision,i.etag_version,
        r.lock_hash,r.overlay_revision FROM bundle_installation i
        JOIN bundle_installation_revision r ON r.org_id=i.org_id AND r.project_id=i.project_id
          AND r.installation_pk=i.installation_pk AND r.revision=i.active_revision
        WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s''',
        (saved['org_id'],saved['project_id'],saved['installation_id'])).fetchone()
    assert installation is not None
    req['installationRef'].update(revision=installation['active_revision'],lockHash=installation['lock_hash'],
        overlayRevision=installation['overlay_revision'])
    saved['_etag']=installation['etag_version']
    saved['_installation_etag']=installation['etag_version']
    conn.execute('''UPDATE extension_runtime_binding SET revision=%s,execution_epoch=%s,config_ref=%s,
        desired_state='enabled',observed_state='ready',enabled=true,operation_fence=false
        WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s''',
        (req['targetRuntimeRevision'],req['targetExecutionEpoch'],Jsonb(req['targetConfigurationRef']),
         saved['org_id'],saved['project_id'],saved['installation_id'],saved['generation']))
    conn.execute('DELETE FROM extension_operation_dispatch_binding WHERE org_id=%s AND project_id=%s',
        (saved['org_id'],saved['project_id']))
    for operation in sorted(ECOMMERCE_GROWTH_OPERATIONS):
        conn.execute('''INSERT INTO extension_operation_dispatch_binding(org_id,project_id,operation_id,
            handler_kind,installation_id,generation,execution_epoch,operation_fence,revision,
            cutover_group_id,cutover_group_revision,updated_by)
            VALUES(%s,%s,%s,'extension',%s,%s,%s,false,1,%s,%s,'fixture-admin')''',
            (saved['org_id'],saved['project_id'],operation,saved['installation_id'],saved['generation'],
             req['sourceExecutionEpoch'],saved['cutover_group_id'],req['expectedGroupRevision']))
    legacy=[dict(operationId=operation,handlerKind='legacy',installationId=None,generation=None,
        executionEpoch=None,operationFence=False,revision=1,cutoverGroupId=str(saved['cutover_group_id']),
        cutoverGroupRevision=req['expectedGroupRevision']-1)
        for operation in sorted(ECOMMERCE_GROWTH_OPERATIONS)]
    conn.execute('''UPDATE extension_dispatch_cutover_operation SET old_dispatch_snapshot=%s
        WHERE org_id=%s AND project_id=%s AND cutover_operation_id=%s''',
        (Jsonb(legacy),saved['org_id'],saved['project_id'],saved['activation_operation_id']))
    conn.execute('''INSERT INTO extension_dispatch_claim_gate(org_id,project_id,cutover_group_id,
        cutover_operation_id,claim_paused,revision,updated_by)
        VALUES(%s,%s,%s,%s,false,2,'fixture-admin')''',
        (saved['org_id'],saved['project_id'],saved['cutover_group_id'],saved['activation_operation_id']))
    seed_operation(conn,saved,kind='configure',operation_id=UUID(req['configureOperationId']),
        revision=req['configureOperationRevision'],binding_revision=req['sourceRuntimeRevision'])
    seed_operation(conn,saved,kind='enable',operation_id=UUID(req['enableOperationId']),
        revision=req['enableOperationRevision'],binding_revision=req['targetRuntimeRevision']-1)
    saved.pop('_etag')
    saved['_login']='refresh_'+uuid4().hex[:16]
    conn.execute('CREATE ROLE '+saved['_login']+' NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS')
    conn.execute('GRANT aos_extension_maintainer,aos_runtime TO '+saved['_login'])
    try: yield conn,saved
    finally:
        conn.rollback();conn.execute('RESET SESSION AUTHORIZATION')
        conn.execute('DROP ROLE '+saved['_login'])


def execute(conn,saved,request=None,actor='fixture-admin'):
    req=saved['request'] if request is None else request
    conn.commit();conn.execute('SET SESSION AUTHORIZATION '+saved['_login'])
    try:
        with conn.transaction():
            conn.execute('SET LOCAL ROLE aos_extension_maintainer')
            conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",
                (saved['org_id'],saved['project_id']))
            receipt_id=conn.execute('SELECT extension_dispatch_configuration_refresh_a0v_068(%s,%s) AS id',
                (Jsonb(req),actor)).fetchone()['id']
            row=conn.execute('SELECT * FROM extension_dispatch_configuration_refresh_receipt WHERE receipt_id=%s',
                (receipt_id,)).fetchone()
            result=decode_receipt(dict(row))
        return result
    finally:conn.execute('RESET SESSION AUTHORIZATION')


def test_atomic_refresh_and_same_key_replay(owner_case):
    conn,saved=owner_case
    operation=sorted(ECOMMERCE_GROWTH_OPERATIONS)[0]
    conn.execute('UPDATE extension_operation_dispatch_binding SET execution_epoch=execution_epoch+1 '
        'WHERE operation_id=%s',(operation,));conn.commit()
    with pytest.raises(psycopg.Error):execute(conn,saved)
    conn.execute('UPDATE extension_operation_dispatch_binding SET execution_epoch=execution_epoch-1 '
        'WHERE operation_id=%s',(operation,));conn.commit()
    assert conn.execute('SELECT count(*) AS n FROM extension_dispatch_configuration_refresh_receipt').fetchone()['n']==0
    first=execute(conn,saved);second=execute(conn,saved)
    assert first==second and first['ref']['revision']==1
    rows=conn.execute('''SELECT execution_epoch,revision,cutover_group_revision
        FROM extension_operation_dispatch_binding ORDER BY operation_id''').fetchall()
    assert len(rows)==len(ECOMMERCE_GROWTH_OPERATIONS)
    assert {row['execution_epoch'] for row in rows}=={saved['request']['targetExecutionEpoch']}
    assert {row['revision'] for row in rows}=={2}
    assert {row['cutover_group_revision'] for row in rows}=={saved['request']['expectedGroupRevision']+1}
    assert conn.execute('SELECT count(*) AS n FROM extension_dispatch_configuration_refresh_receipt').fetchone()['n']==1
    next_request=deepcopy(saved['request'])
    next_request.update(sourceAuthorityRef=first['ref'],
        expectedGroupRevision=next_request['expectedGroupRevision']+1,
        sourceRuntimeRevision=next_request['targetRuntimeRevision'],
        sourceExecutionEpoch=next_request['targetExecutionEpoch'],
        sourceConfigurationRef=deepcopy(next_request['targetConfigurationRef']),
        targetRuntimeRevision=next_request['targetRuntimeRevision']+3,
        targetExecutionEpoch=next_request['targetExecutionEpoch']+2,
        configureOperationId=str(uuid4()),enableOperationId=str(uuid4()),
        configureOperationRevision=1,enableOperationRevision=1,idempotencyKey='second-refresh')
    next_request['targetConfigurationRef'].update(
        revision=next_request['targetConfigurationRef']['revision']+1,hash='sha256:'+'e'*64)
    next_saved=dict(saved,request=next_request,_etag=saved['_installation_etag'])
    conn.execute('''UPDATE extension_runtime_binding SET revision=%s,execution_epoch=%s,config_ref=%s
        WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s''',
        (next_request['targetRuntimeRevision'],next_request['targetExecutionEpoch'],
         Jsonb(next_request['targetConfigurationRef']),saved['org_id'],saved['project_id'],
         saved['installation_id'],saved['generation']))
    seed_operation(conn,next_saved,kind='configure',operation_id=UUID(next_request['configureOperationId']),
        revision=1,binding_revision=next_request['sourceRuntimeRevision'])
    seed_operation(conn,next_saved,kind='enable',operation_id=UUID(next_request['enableOperationId']),
        revision=1,binding_revision=next_request['targetRuntimeRevision']-1)
    conn.commit()
    latest=execute(conn,saved,request=next_request)
    assert latest['ref']['revision']==2
    assert conn.execute('SELECT count(*) AS n FROM extension_dispatch_configuration_refresh_receipt').fetchone()['n']==2
    with pytest.raises(psycopg.Error,match='idempotency conflict'):
        execute(conn,saved)
    assert_refreshed_dispatch_lifecycle(owner_case,latest,next_request)


def assert_refreshed_dispatch_lifecycle(owner_case,refresh,request):
    conn,saved=owner_case
    scope=TenantScope(saved['org_id'],saved['project_id'])
    conn.commit();conn.execute('SET SESSION AUTHORIZATION '+saved['_login'])
    try:
        with conn.transaction():
            conn.execute('SET LOCAL ROLE aos_runtime')
            conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",scope.key)
            operation=RuntimeOperationStore().accept(conn,org_id=scope.org_id,project_id=scope.project_id,
                installation_id=UUID(str(saved['installation_id'])),kind='disable',idempotency_key='refresh-disable',
                requested_by='runtime-owner',expected_installation_etag=saved['_installation_etag'],
                deadline=datetime.now(timezone.utc)+timedelta(minutes=5),binding_target={
                    'generation':str(saved['generation']),'bindingRevision':request['targetRuntimeRevision']})
            fenced=RuntimeBindingStore().fence(conn,org_id=scope.org_id,project_id=scope.project_id,
                installation_id=UUID(str(saved['installation_id'])),generation=UUID(str(saved['generation'])),
                operation_id=operation.operation_id,expected_operation_revision=operation.revision,
                expected_binding_revision=request['targetRuntimeRevision'])
            dependent=EcommerceGrowthDisableDependent()
            fence_receipt=dependent.after_runtime_fenced(conn,org_id=scope.org_id,
                project_id=scope.project_id,runtime_operation_id=operation.operation_id)
            assert fence_receipt is not None
            assert fence_receipt.configuration_refresh_ref is not None
            assert fence_receipt.configuration_refresh_ref.resource_id==refresh['ref']['resourceId']
        with conn.transaction():
            conn.execute('SET LOCAL ROLE aos_runtime')
            conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",scope.key)
            operations=RuntimeOperationStore();revision=fenced.revision
            for phase in ('draining','committing'):
                revision=operations.advance(conn,org_id=scope.org_id,project_id=scope.project_id,
                    operation_id=operation.operation_id,expected_revision=revision,phase=phase).revision
            conn.execute("""UPDATE extension_runtime_binding
                SET desired_state='disabled',observed_state='unknown',revision=revision+1
                WHERE org_id=%s AND project_id=%s AND installation_id=%s""",
                (*scope.key,UUID(str(saved['installation_id']))))
            conn.execute('''UPDATE extension_runtime_operation SET revision=revision+1
                WHERE org_id=%s AND project_id=%s AND operation_id=%s''',
                (*scope.key,operation.operation_id))
            revision+=1
            operations._event(conn,*scope.key,operation.operation_id,revision,'disabled_committed',
                {'resourcesRetained':True})
            operations.advance(conn,org_id=scope.org_id,project_id=scope.project_id,
                operation_id=operation.operation_id,expected_revision=revision,phase='succeeded')
        with conn.transaction():
            conn.execute('SET LOCAL ROLE aos_runtime')
            conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",scope.key)
            detach=EcommerceGrowthDisableDependent().after_runtime_disabled(conn,org_id=scope.org_id,
                project_id=scope.project_id,runtime_operation_id=operation.operation_id)
            assert detach is not None and detach.status=='detached'
            assert detach.configuration_refresh_ref is not None
            assert detach.configuration_refresh_ref.resource_id==refresh['ref']['resourceId']
    finally:
        conn.execute('RESET SESSION AUTHORIZATION')
