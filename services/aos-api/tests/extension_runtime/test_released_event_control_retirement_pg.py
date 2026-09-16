import importlib.util
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timedelta,timezone
from uuid import uuid4

import pytest

from aos_api.tenant_scope import TenantScope
from test_event_control_dispatch_lifecycle_pg import dispatch_db,_request,_transition
from test_ecommerce_growth_cutover_pg import database,_resumed_activation


@pytest.fixture
def released_db(dispatch_db):
    root=Path(__file__).resolve().parents[2]
    spec=importlib.util.spec_from_file_location('a0v_074_test',
        root/'alembic/versions/a0v_074_released_event_control_retirement.py')
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    migration.op=SimpleNamespace(execute=lambda statement:dispatch_db.owner.execute(
        statement.replace('public.',dispatch_db.schema+'.')))
    migration.upgrade()
    return dispatch_db


def _released(released_db,scope):
    original,_prepared=_resumed_activation(released_db,scope)
    owner=released_db.owner
    owner.execute("INSERT INTO meta_membership VALUES(%s,%s,'fixture-operator','admin')",scope.key)
    runtime=owner.execute('''SELECT * FROM extension_runtime_binding
        WHERE installation_id=%s AND generation=%s''',
        (original.target_installation_id,original.target_generation)).fetchone()
    group=owner.execute('''SELECT cutover_group_id,cutover_group_revision
        FROM extension_operation_dispatch_binding LIMIT 1''').fetchone()
    ids=(str(original.target_installation_id),str(original.target_generation),
         str(group['cutover_group_id']))
    expand=_request(ids,'expand',group['cutover_group_revision'],'released-expand')
    expand['installationRef']['revision']=runtime['installation_revision']
    expand['executionEpoch']=runtime['execution_epoch'];expand['runtimeRevision']=runtime['revision']
    _transition(released_db,scope,expand)
    owner.execute('''UPDATE extension_runtime_binding SET enabled=false,operation_fence=true,
        observed_state='unknown',execution_epoch=execution_epoch+1,revision=7
        WHERE installation_id=%s AND generation=%s''',
        (original.target_installation_id,original.target_generation))
    operation=uuid4()
    owner.execute('''INSERT INTO extension_runtime_operation(org_id,project_id,operation_id,
        installation_id,kind,idempotency_key,request_hash,requested_by,expected_installation_etag,
        status,phase,deadline) VALUES(%s,%s,%s,%s,'runtime-apply','released-fixture',%s,
        'runtime-owner',1,'succeeded','succeeded',%s)''',(*scope.key,operation,
        original.target_installation_id,'sha256:'+'9'*64,
        datetime.now(timezone.utc)+timedelta(minutes=5)))
    for index in range(3):
        owner.execute('''INSERT INTO extension_runtime_resource_lease(org_id,project_id,
            resource_id,operation_id,owner_token_ref,generation,package_id,package_hash,
            engine_context,resource_name,cleanup_state,expires_at,observed_release)
            VALUES(%s,%s,%s,%s,'owner',%s,%s,%s,'fixture',%s,'released',%s,true)''',
            (*scope.key,uuid4(),operation,original.target_generation,f'package-{index}',
             'sha256:'+str(index+1)*64,f'resource-{uuid4()}',datetime.now(timezone.utc)))
    return ids,runtime['installation_revision'],group['cutover_group_revision']+1,runtime['execution_epoch']


def test_released_runtime_can_only_fence_then_shrink_after_full_release(released_db):
    scope=TenantScope('org-org','dev-project')
    ids,installation_revision,group_revision,event_epoch=_released(released_db,scope)
    fence=_request(ids,'fence',group_revision,'released-fence')
    fence['installationRef']['revision']=installation_revision
    fence['executionEpoch']=event_epoch
    fence['runtimeRevision']=7
    fenced=_transition(released_db,scope,fence)
    assert fenced['releasedRuntimeRecovery'] is True
    shrink=_request(ids,'shrink',group_revision+1,'released-shrink')
    shrink['installationRef']['revision']=installation_revision
    shrink['executionEpoch']=event_epoch
    shrink['runtimeRevision']=7
    shrunk=_transition(released_db,scope,shrink)
    assert shrunk['releasedRuntimeRecovery'] is True
    assert len(shrunk['afterSnapshot'])==9


def test_released_retirement_rejects_partial_resource_release(released_db):
    scope=TenantScope('org-org','dev-project')
    ids,installation_revision,group_revision,event_epoch=_released(released_db,scope)
    released_db.owner.execute('''UPDATE extension_runtime_resource_lease
        SET cleanup_state='pending',observed_release=false
        WHERE resource_id=(SELECT resource_id FROM extension_runtime_resource_lease LIMIT 1)''')
    request=_request(ids,'fence',group_revision,'partial-release-fence')
    request['installationRef']['revision']=installation_revision
    request['executionEpoch']=event_epoch
    request['runtimeRevision']=7
    with pytest.raises(Exception,match='event dispatch runtime drifted'):
        _transition(released_db,scope,request)
    assert released_db.owner.execute("""SELECT count(*) AS n FROM
        extension_event_control_dispatch_receipt WHERE phase='fence'""").fetchone()['n']==0
