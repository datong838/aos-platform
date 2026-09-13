from types import SimpleNamespace

import pytest

from test_ui_read_store_pg import admission, queue, attempt_case, database, SCOPE, pytestmark
from aos_api.ecommerce_runtime_workshop_catalog import RuntimeWorkshopCatalog
from aos_api.extension_runtime.ui_read_admission import RuntimeUiReadAdmission
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict


@pytest.fixture
def signed_admission(admission, monkeypatch):
    conn, request = admission
    target = request.target
    entry = SimpleNamespace(installationId=target.installationId,
        installationRevision=target.installationRevision, generation=target.generation,
        executionEpoch=target.executionEpoch, bindingRevision=target.bindingRevision,
        module=SimpleNamespace(module_id=request.moduleId, route=target.route,
            permissions=SimpleNamespace(roles=('reader',), markings=())),
        ui=SimpleNamespace(initialRoute=target.route, routeClaims=(target.route,),
            resourceHash=target.resourceHash, readOperationClaims=(request.operationId,),
            commandOperationClaims=()))
    response = SimpleNamespace(tenant=SimpleNamespace(orgId=SCOPE.org_id,projectId=SCOPE.project_id),
                               items=[entry], count=1)
    # Catalog hash verification is covered by its own tests. These PG tests isolate
    # admission ordering against real membership locks and delivery persistence.
    catalog = RuntimeWorkshopCatalog(source=None, loader=None, view_reader=None)
    facts=[]
    def current_catalog(**kwargs):
        facts.append(kwargs)
        return response
    monkeypatch.setattr(catalog,'list_modules',current_catalog)
    return conn,request,RuntimeUiReadAdmission(catalog=catalog),response,entry,facts


def accept(case):
    conn,request,service,*_=case
    with conn.transaction():
        return service.enqueue(conn=conn,scope=SCOPE,subject='reader',required_markings=(),
                               idempotency_key='page-read',request=request)


def test_current_read_is_enqueued_once_with_persisted_principal(signed_admission):
    first = accept(signed_admission)
    assert accept(signed_admission) == first
    conn,_,_,_,_,facts=signed_admission
    assert facts[0] == dict(org_id=SCOPE.org_id,project_id=SCOPE.project_id,roles=('reader',),markings=())
    assert conn.execute('SELECT count(*) FROM extension_runtime_ui_read_request').fetchone()==(1,)


@pytest.mark.parametrize('failure',['scope','missing','duplicate','role','marking','hash','epoch','route','read-claim','command-only'])
def test_invalid_current_catalog_never_persists(signed_admission,failure):
    conn,request,_,response,entry,_=signed_admission
    if failure=='scope':response.tenant.orgId='dev-org'
    if failure=='missing':response.items=[];response.count=0
    if failure=='duplicate':response.items.append(entry);response.count=2
    if failure=='role':entry.module.permissions.roles=('admin',)
    if failure=='marking':entry.module.permissions.markings=('secret',)
    if failure=='hash':entry.ui.resourceHash='sha256:'+'b'*64
    if failure=='epoch':entry.executionEpoch+=1
    if failure=='route':entry.module.route='/workshop/customer'
    if failure in ('read-claim','command-only'):entry.ui.readOperationClaims=()
    if failure=='command-only':entry.ui.commandOperationClaims=(request.operationId,)
    with pytest.raises(RuntimeConflict):accept(signed_admission)
    assert conn.execute('SELECT count(*) FROM extension_runtime_ui_read_request').fetchone()==(0,)


def test_revocation_denies_replay_before_catalog_read(signed_admission):
    accept(signed_admission)
    conn,_,_,_,_,facts=signed_admission
    conn.execute("DELETE FROM meta_membership WHERE subject='reader'")
    with pytest.raises(RuntimeConflict,match='membership'):accept(signed_admission)
    assert len(facts)==1
    assert conn.execute('SELECT count(*) FROM extension_runtime_ui_read_request').fetchone()==(1,)


def test_resource_change_denies_existing_key(signed_admission):
    accept(signed_admission)
    conn,_,_,_,entry,_=signed_admission
    entry.ui.resourceHash='sha256:'+'b'*64
    with pytest.raises(RuntimeConflict):accept(signed_admission)
    assert conn.execute('SELECT count(*) FROM extension_runtime_ui_read_request').fetchone()==(1,)
