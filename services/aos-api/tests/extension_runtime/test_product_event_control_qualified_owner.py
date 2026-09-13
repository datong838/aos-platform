"""Qualification composition with named source/release doubles, not signatures."""
import json
from types import SimpleNamespace
from test_product_event_qualified_owner import setup
from aos_api.ecommerce_product_event_control_qualified_owner import ProductEventControlQualifiedOwner,CONTROL_CONTRACT
import pytest


@pytest.fixture
def control(setup):
    original,conn,scope,record,calls,artifacts=setup
    artifacts.read_artifact=lambda *a:json.dumps(CONTROL_CONTRACT).encode()
    owner=ProductEventControlQualifiedOwner(selections=original._selections,installation_store=original._store,
        artifacts=artifacts,release_policy=original._policy)
    return owner,conn,scope,record,calls,artifacts


def test_control_source_path_accepts_only_control_contract(control):
    owner,conn,scope,record,calls,_=control
    assert owner.run_current_snapshot(conn,scope=scope,ref=record.ref,actor='fixture',execute=lambda *a:'done')=='done'
    assert calls.count('qualification')==2 and calls.count('source')==1


def test_save_contract_cannot_authorize_control(control):
    from aos_api.ecommerce_product_event_qualified_owner import EVENT_CONTRACT
    owner,conn,scope,record,_,artifacts=control
    artifacts.read_artifact=lambda *a:json.dumps(EVENT_CONTRACT).encode()
    with pytest.raises(ValueError):owner.run_current_snapshot(conn,scope=scope,ref=record.ref,actor='fixture',execute=lambda *a:pytest.fail('unauthorized'))


def test_disable_qualification_does_not_call_source(control):
    owner,conn,scope,record,calls,_=control
    draft=record.draft
    owner._source.run_current_snapshot=lambda *a,**kw:pytest.fail('disable called source')
    current=dict(installation_id=draft.installation_ref.installation_id,revision=draft.installation_ref.revision,
        etag_version=1,lock_hash=draft.installation_ref.lock_hash,overlay_revision=draft.installation_ref.overlay_revision,generation=draft.generation,execution_epoch=draft.execution_epoch,role='aos_runtime',org_id=scope.org_id,project_id=scope.project_id)
    conn.execute=lambda *a,**kw:SimpleNamespace(fetchone=lambda:current)
    dispatch=SimpleNamespace(installation_id=draft.installation_ref.installation_id,generation=draft.generation,
        execution_epoch=draft.execution_epoch,operation_id='ecommerce_growth_event_control')
    assert owner.run_without_source(conn,scope=scope,dispatch=dispatch,execute=lambda:'stopped')=='stopped'
    assert calls.count('qualification')==2 and 'source' not in calls


def test_disable_generation_drift_fails(control):
    owner,conn,scope,record,_,_=control;draft=record.draft
    conn.execute=lambda *a,**kw:SimpleNamespace(fetchone=lambda:dict(installation_id=draft.installation_ref.installation_id,
        revision=draft.installation_ref.revision,etag_version=1,lock_hash=draft.installation_ref.lock_hash,overlay_revision=draft.installation_ref.overlay_revision,
        generation='other',execution_epoch=draft.execution_epoch,role='aos_runtime',org_id=scope.org_id,project_id=scope.project_id))
    dispatch=SimpleNamespace(installation_id=draft.installation_ref.installation_id,generation=draft.generation,
        execution_epoch=draft.execution_epoch,operation_id='ecommerce_growth_event_control')
    with pytest.raises(ValueError):owner.run_without_source(conn,scope=scope,dispatch=dispatch,execute=lambda:pytest.fail('drift'))


def test_control_contract_is_exported_source_artifact():
    from pathlib import Path
    from aos_api.ecommerce_product_event_control_qualified_owner import CONTROL_CONTRACT_PATH
    path=Path(__file__).resolve().parents[4]/'bundles/solutions/ecommerce-growth'/CONTROL_CONTRACT_PATH
    assert json.loads(path.read_text())==CONTROL_CONTRACT


def test_transaction_bridge_rejects_arbitrary_owner():
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    with pytest.raises(TypeError):HostTransaction(object()).run_current_event_control(
        object(),scope=None,dispatch=None,execute=lambda:None)


def test_control_qualification_rejects_deferred_result(control):
    owner,conn,scope,record,_,_=control
    def later(*args):yield 'outside'
    with pytest.raises(ValueError,match='locked transaction'):
        owner.run_current_snapshot(conn,scope=scope,ref=record.ref,actor='fixture',execute=later)
