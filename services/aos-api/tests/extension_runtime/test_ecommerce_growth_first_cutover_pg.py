from uuid import uuid4

import pytest

from aos_api.ecommerce_growth_cutover import EcommerceGrowthCutoverStore,EcommerceGrowthCutoverBlocked
from aos_api.ecommerce_growth_registration import FirstDispatchRegistrationService
from aos_api.ecommerce_growth_registration_origin import RegistrationReceiptRef
from aos_api.tenant_scope import TenantScope
from test_ecommerce_growth_cutover_pg import (database,pytestmark,_seed,_connection,_commit_request,
    _finalize_request,_validate_ref,_rollback_request)


@pytest.mark.parametrize('finish',['resume','rollback','prepare_denied','pause_denied','commit_denied'])
def test_first_fenced_origin_is_checked_at_each_forward_stage(database,monkeypatch,finish):
    scope=TenantScope('org-org','dev-project')
    ref=RegistrationReceiptRef(resourceType='FirstDispatchRegistrationReceipt',resourceId=str(uuid4()),
        revision=1,contentHash='sha256:'+'b'*64)
    request=_seed(database,scope,pending_receipt=False,expected_group_revision=1,registration_ref=ref)
    service=object.__new__(FirstDispatchRegistrationService);seen=[];deny=[]
    def gate(conn,**kwargs):
        state=conn.execute('SELECT current_user AS role,pg_backend_pid() AS pid,txid_current() AS tx').fetchone()
        assert state['role']=='aos_runtime' and kwargs['actor']=='runtime-owner'
        assert kwargs['receipt_ref']==ref and kwargs['binding_revision']==request.target_runtime_revision
        assert len(kwargs['dispatch_snapshot'])==9
        assert all(r['operationFence'] is True and r['revision']==1 for r in kwargs['dispatch_snapshot'])
        seen.append(state)
        if deny:raise PermissionError('current assets revoked')
        return dict(receiptRef=ref.model_dump(),requestHash='sha256:'+'c'*64,
            currentConfigurationValidated=True,currentReleaseValidated=True,runtimeStateValidated=False,executable=False)
    monkeypatch.setattr(service,'validate_cutover_registration_assets_in_transaction',gate,raising=False)
    store=EcommerceGrowthCutoverStore(_connection(database),schema=database.schema,registration_service=service)
    if finish=='prepare_denied':
        deny.append(True)
        with pytest.raises(PermissionError):store.prepare_activation(scope,request,actor='runtime-owner')
        assert database.owner.execute('SELECT count(*) AS n FROM extension_dispatch_cutover_operation').fetchone()['n']==0
        return
    prepared=store.prepare_activation(scope,request,actor='runtime-owner')
    assert prepared.registration_receipt_ref==ref and all(r['operationFence'] for r in prepared.old_dispatch_snapshot)
    commit_request=_commit_request(prepared)
    if finish=='pause_denied':
        deny.append(True)
        with pytest.raises(PermissionError):store.begin_activation_commit(scope,commit_request,actor='runtime-owner')
        assert database.owner.execute('SELECT status FROM extension_dispatch_cutover_operation').fetchone()['status']=='prepared'
        return
    store.begin_activation_commit(scope,commit_request,actor='runtime-owner')
    if finish=='commit_denied':
        deny.append(True)
        with pytest.raises(PermissionError):store.commit_activation(scope,commit_request,actor='runtime-owner')
        assert database.owner.execute('SELECT status FROM extension_dispatch_cutover_operation').fetchone()['status']=='draining'
        return
    committed=store.commit_activation(scope,commit_request,actor='runtime-owner')
    final_request=_finalize_request(committed)
    if finish=='resume':
        validated=store.validate_activation(scope,final_request,actor='runtime-owner')
        store.resume_activation(scope,final_request,validate_receipt_ref=_validate_ref(validated),actor='runtime-owner')
        assert len(seen)==6
        assert database.owner.execute("SELECT bool_and(handler_kind='extension' AND NOT operation_fence) AS valid FROM extension_operation_dispatch_binding").fetchone()['valid']
    else:
        deny.append(True)
        with pytest.raises(PermissionError,match='current assets revoked'):
            store.validate_activation(scope,final_request,actor='runtime-owner')
        rollback=_rollback_request(database,scope,prepared,committed)
        store.prepare_validation_rollback(scope,rollback,actor='runtime-owner')
        store.commit_validation_rollback(scope,rollback,actor='runtime-owner')
        assert database.owner.execute("SELECT bool_and(handler_kind='legacy' AND operation_fence) AS valid FROM extension_operation_dispatch_binding").fetchone()['valid']


def test_first_registration_requires_configured_real_service(database):
    ref=RegistrationReceiptRef(resourceType='FirstDispatchRegistrationReceipt',resourceId=str(uuid4()),revision=1,contentHash='sha256:'+'b'*64)
    scope=TenantScope('org-org','dev-project')
    request=_seed(database,scope,pending_receipt=False,expected_group_revision=1,registration_ref=ref)
    with pytest.raises(EcommerceGrowthCutoverBlocked,match='registration activation'):
        EcommerceGrowthCutoverStore(_connection(database),schema=database.schema).prepare_activation(scope,request,actor='runtime-owner')


def test_old_approval_cannot_authorize_first_registration(database,monkeypatch):
    scope=TenantScope('org-org','dev-project')
    request=_seed(database,scope,pending_receipt=False,expected_group_revision=1)
    ref=RegistrationReceiptRef(resourceType='FirstDispatchRegistrationReceipt',resourceId=str(uuid4()),revision=1,contentHash='sha256:'+'b'*64)
    request=request.model_copy(update={'registration_receipt_ref':ref})
    database.owner.execute('UPDATE extension_operation_dispatch_binding SET operation_fence=true,revision=1')
    service=object.__new__(FirstDispatchRegistrationService)
    monkeypatch.setattr(service,'validate_cutover_registration_assets_in_transaction',lambda *a,**k:dict(
        receiptRef=ref.model_dump(),currentConfigurationValidated=True,currentReleaseValidated=True,
        runtimeStateValidated=False,executable=False))
    store=EcommerceGrowthCutoverStore(_connection(database),schema=database.schema,registration_service=service)
    with pytest.raises(EcommerceGrowthCutoverBlocked,match='approval is not bound'):
        store.prepare_activation(scope,request,actor='runtime-owner')
    assert database.owner.execute('SELECT count(*) AS n FROM extension_dispatch_cutover_operation').fetchone()['n']==0
