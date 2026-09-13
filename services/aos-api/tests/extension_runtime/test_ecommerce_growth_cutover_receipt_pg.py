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


@pytest.mark.parametrize('finish',['prepare','pause','commit','validate','resume','rollback'])
def test_all_history_stages(database,monkeypatch,finish):
    from test_ecommerce_growth_cutover_pg import _commit_request,_finalize_request,_validate_ref,_rollback_request
    scope=TenantScope('org-org','dev-project')
    request=_seed(database,scope,pending_receipt=False)
    store=EcommerceGrowthCutoverStore(_connection(database),schema=database.schema)
    prepare=store.prepare_activation(scope,request,actor='runtime-owner')
    expected=['prepare']
    if finish!='prepare':
        command=_commit_request(prepare)
        store.begin_activation_commit(scope,command,actor='runtime-owner');expected.append('pause')
    if finish not in ('prepare','pause'):
        commit=store.commit_activation(scope,command,actor='runtime-owner');expected.append('commit')
    if finish in ('validate','resume'):
        final=_finalize_request(commit)
        validated=store.validate_activation(scope,final,actor='runtime-owner');expected.append('validate')
    if finish=='resume':
        store.resume_activation(scope,final,validate_receipt_ref=_validate_ref(validated),actor='runtime-owner');expected.append('resume')
    if finish=='rollback':
        rollback=_rollback_request(database,scope,prepare,commit)
        store.prepare_validation_rollback(scope,rollback,actor='runtime-owner')
        store.commit_validation_rollback(scope,rollback,actor='runtime-owner')
    service=object.__new__(FirstDispatchRegistrationService)
    monkeypatch.setattr(service,'_authorize_receipt_access',lambda *a:None)
    store=EcommerceGrowthCutoverStore(_connection(database),schema=database.schema,registration_service=service)
    history=store.read_activation_history(scope=scope,installation_id=str(request.target_installation_id),idempotency_key=request.idempotency_key,actor='reader')
    assert history['historical'] is True and history['executable'] is False
    assert list(history['activationReceipts'])==expected
    if finish=='rollback':
        assert len(history['rollbacks'])==1
        assert list(history['rollbacks'][0]['receipts'])==['fence','drain','rollback']
    else:assert history['rollbacks']==[]


@pytest.mark.parametrize('defect',['missing-event','wrong-parent'])
def test_history_rejects_incomplete_or_unrelated_phase(database,monkeypatch,defect):
    from test_ecommerce_growth_cutover_pg import _commit_request
    from aos_api.ecommerce_growth_cutover import CutoverExactRef
    scope=TenantScope('org-org','dev-project')
    request=_seed(database,scope,pending_receipt=False)
    store=EcommerceGrowthCutoverStore(_connection(database),schema=database.schema)
    prepare=store.prepare_activation(scope,request,actor='runtime-owner')
    store.begin_activation_commit(scope,_commit_request(prepare),actor='runtime-owner')
    service=object.__new__(FirstDispatchRegistrationService)
    monkeypatch.setattr(service,'_authorize_receipt_access',lambda *a:None)
    store=EcommerceGrowthCutoverStore(_connection(database),schema=database.schema,registration_service=service)
    if defect=='missing-event':
        # A receipt can exist while its join finds no corresponding valid event.
        monkeypatch.setattr(store,'_load_phase_receipt',lambda *a:None)
    else:
        decode=store._phase_receipt
        def wrong_parent(*args,**kwargs):
            result=decode(*args,**kwargs)
            foreign=CutoverExactRef(resourceType='CutoverPrepareReceipt',resourceId=str(uuid4()),revision=1,contentHash='sha256:'+'b'*64)
            return result.model_copy(update={'prepare_receipt_ref':foreign})
        monkeypatch.setattr(store,'_phase_receipt',wrong_parent)
    with pytest.raises(EcommerceGrowthCutoverConflict,match='linkage or completeness'):
        store.read_activation_history(scope=scope,installation_id=str(request.target_installation_id),idempotency_key=request.idempotency_key,actor='reader')
