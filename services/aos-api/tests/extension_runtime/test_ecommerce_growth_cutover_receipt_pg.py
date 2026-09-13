from uuid import uuid4

import pytest

from aos_api.ecommerce_growth_cutover import EcommerceGrowthCutoverStore, EcommerceGrowthCutoverBlocked, EcommerceGrowthCutoverConflict
from aos_api.ecommerce_growth_registration import FirstDispatchRegistrationService
from aos_api.tenant_scope import TenantScope
from test_ecommerce_growth_cutover_pg import database, pytestmark, _seed, _connection


def test_unwired_read_does_not_connect():
    store=EcommerceGrowthCutoverStore(lambda scope: pytest.fail('unwired connection'))
    with pytest.raises(EcommerceGrowthCutoverBlocked):
        store.read_prepare_receipt(scope=TenantScope('org-org','dev-project'), installation_id=str(uuid4()), idempotency_key='key', actor='actor')


@pytest.mark.parametrize('case',['ok','missing','wrong-installation','cross-tenant','denied','drift'])
def test_actual_original_key_read(database, monkeypatch, case):
    scope=TenantScope('org-org','dev-project')
    request=_seed(database,scope,pending_receipt=False)
    store=EcommerceGrowthCutoverStore(_connection(database),schema=database.schema)
    prepared=store.prepare_activation(scope,request,actor='runtime-owner')
    service=object.__new__(FirstDispatchRegistrationService)
    checks=[]
    def authorize(conn, current_scope, installation_id, actor):
        assert conn.execute('SELECT current_user AS role').fetchone()['role']=='aos_runtime'
        checks.append((current_scope,installation_id,actor))
        if case=='denied':raise PermissionError('current access denied')
    monkeypatch.setattr(service,'_authorize_receipt_access',authorize)
    store=EcommerceGrowthCutoverStore(_connection(database),schema=database.schema,registration_service=service)
    if case=='drift':
        decode=store._receipt
        def corrupt(current_scope,row,*,replayed):
            return decode(current_scope,{**row,'content_hash':'sha256:'+'0'*64},replayed=replayed)
        monkeypatch.setattr(store,'_receipt',corrupt)
    kwargs=dict(scope=TenantScope('dev-org','dev-project') if case=='cross-tenant' else scope,
        installation_id=str(uuid4()) if case=='wrong-installation' else str(request.target_installation_id),
        idempotency_key='not-found' if case=='missing' else request.idempotency_key,actor='reader')
    error=PermissionError if case=='denied' else EcommerceGrowthCutoverConflict if case=='drift' else LookupError
    if case=='ok':
        result=store.read_prepare_receipt(**kwargs)
        assert result['historical'] is True and result['executable'] is False
        assert result['receipt']['receiptId']==str(prepared.receipt_id)
        assert result['receipt']['contentHash']==prepared.content_hash
    else:
        with pytest.raises(error):store.read_prepare_receipt(**kwargs)
    assert len(checks)==1
    assert database.owner.execute('SELECT status FROM extension_dispatch_cutover_operation').fetchone()['status']=='prepared'
