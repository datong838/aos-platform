"""Real ledger/Owner composition, with explicitly fake current asset authority."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_lifecycle_pg import database, pytestmark
from test_pipeline_source_selection_schema_pg import ledger
from test_pipeline_source_selection_owner_pg import owner_case, approve
from aos_api.pipeline_runtime_control_contracts import PipelineRuntimeControlDraft
from aos_api.pipeline_runtime_control_owner import PipelineRuntimeControlOwner
from aos_api.tenant_scope import TenantScope
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict, RuntimeRevisionConflict


@pytest.fixture
def control_case(owner_case):
    conn,selections,selection,calls=owner_case
    selection_ref=approve(conn,selections,selection)
    conn.execute('RESET ROLE')
    path=Path(__file__).resolve().parents[2]/'alembic/versions/a0v_023_pipeline_runtime_control.py'
    spec=importlib.util.spec_from_file_location('control_owner_test_migration',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.op=SimpleNamespace(execute=conn.execute);module.upgrade()
    conn.execute('SET ROLE aos_runtime')
    body=selection.model_dump();body.pop('schema_version');body['source_selection_ref']=selection_ref
    draft=PipelineRuntimeControlDraft.model_validate(body)
    return conn,PipelineRuntimeControlOwner(selections=selections),draft,selections,selection,calls


def append(conn,owner,draft,key='first',previous=None):
    with conn.transaction():return owner.append(conn,draft=draft,actor='test-actor',idempotency_key=key,previous_ref=previous)


def consume(conn,owner,draft,ref):
    with conn.transaction():return owner.run_current(conn,scope=TenantScope(draft.org_id,draft.project_id),ref=ref,
        actor='test-actor',execute=lambda item,spec:item.row_limit)


def test_control_append_replay_and_latest_consumption(control_case):
    conn,owner,draft,_,_,calls=control_case
    first=append(conn,owner,draft)
    assert append(conn,owner,draft)==first
    assert consume(conn,owner,draft,first)==100
    second=append(conn,owner,draft,'next',first)
    with pytest.raises(RuntimeRevisionConflict):consume(conn,owner,draft,first)
    assert consume(conn,owner,draft,second)==100
    with pytest.raises(RuntimeRevisionConflict):append(conn,owner,draft,'stale',first)
    assert conn.execute('SELECT count(*) FROM pipeline_runtime_control_revision').fetchone()==(2,)
    assert len(calls)>=6


def test_control_cannot_expand_selection_or_reuse_after_selection_change(control_case):
    conn,owner,draft,selections,selection,_=control_case
    with pytest.raises(ValueError):append(conn,owner,draft.model_copy(update={'row_limit':999}))
    first=append(conn,owner,draft)
    approve(conn,selections,selection,'new-selection',draft.source_selection_ref)
    with pytest.raises(RuntimeRevisionConflict):append(conn,owner,draft)
    with pytest.raises(RuntimeRevisionConflict):consume(conn,owner,draft,first)
    assert conn.execute('SELECT count(*) FROM pipeline_runtime_control_revision').fetchone()==(1,)


def test_control_replay_cannot_bypass_current_denial(control_case):
    conn,owner,draft,selections,_,_=control_case
    first=append(conn,owner,draft)
    def deny(*args):raise PermissionError('named current denial')
    selections._guarded=deny
    with pytest.raises(PermissionError):append(conn,owner,draft)
    with pytest.raises(PermissionError):consume(conn,owner,draft,first)


def test_control_append_is_owned_by_outer_transaction(control_case):
    conn,owner,draft,_,_,_=control_case
    with pytest.raises(RuntimeError,match='rollback'),conn.transaction():
        owner.append(conn,draft=draft,actor='test-actor',idempotency_key='rollback')
        raise RuntimeError('rollback')
    assert conn.execute('SELECT count(*) FROM pipeline_runtime_control_revision').fetchone()==(0,)


@pytest.mark.parametrize('mode',['current','control_superseded','selection_superseded','spec_changed','denied','deferred'])
def test_snapshot_consumption_retains_current_control_and_selection(control_case,mode):
    from aos_api.pipeline_source_selection import MappingReadSpec
    from aos_api.pipeline_snapshot_materialization import compile_snapshot_mapping
    conn,owner,draft,selections,selection,_=control_case
    ref=append(conn,owner,draft)
    if mode=='control_superseded':append(conn,owner,draft,'next',ref)
    if mode=='selection_superseded':approve(conn,selections,selection,'next-selection',draft.source_selection_ref)
    mapping={'source_table':'ns_site','target_ot':'Shop','primary_key':'site_id','incremental_strategy':'snapshot',
        'site_filter':'site_id=1','field_mappings':[{'source':'site_id','target':'siteId','type':'int'},
            {'source':'site_name','target':'name','type':'string'}],
        'validation':{'required':['site_id','site_name']},'unique_key_pattern':'niushop:{pk}',
        'snapshot_materialization':{'schema_version':'aos.snapshot-materialization/v1','platform':'niushop',
            'shop_key':'site_id','source_timezone':'+08:00','property_defaults':{}}}
    if mode=='spec_changed':mapping['source_table']='different'
    spec=MappingReadSpec(mapping['source_table'],'Shop','site_id',('site_id','site_name'),(('site_id',1),))
    compiled=compile_snapshot_mapping(mapping,spec)
    # Explicit fake asset gate. The real asset compile seam is tested separately.
    def fake_guard(db,item,actor,callback,*,snapshot=False):
        assert snapshot is True
        if mode=='denied':raise PermissionError('current denied')
        return callback(compiled)
    selections._guarded=fake_guard
    calls=[]
    def execute(current,value):
        calls.append(value)
        assert current==draft and value is compiled
        return (x for x in []) if mode=='deferred' else value.shop_id
    with conn.transaction():
        if mode=='current':
            assert owner.run_current_snapshot(conn,scope=TenantScope(draft.org_id,draft.project_id),ref=ref,actor='test-actor',execute=execute)=='1'
        else:
            with pytest.raises((RuntimeConflict,PermissionError,ValueError)):
                owner.run_current_snapshot(conn,scope=TenantScope(draft.org_id,draft.project_id),ref=ref,actor='test-actor',execute=execute)
    assert len(calls)==(1 if mode in {'current','deferred'} else 0)
