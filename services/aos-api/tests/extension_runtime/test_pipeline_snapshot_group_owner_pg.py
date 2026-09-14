"""Real current-control ledgers/transactions; signed asset checks are explicit doubles."""
import pytest
from test_lifecycle_pg import database,pytestmark
from test_pipeline_source_selection_schema_pg import ledger
from test_pipeline_source_selection_owner_pg import owner_case,approve
from test_pipeline_runtime_control_owner_pg import control_case,append
from aos_api.pipeline_runtime_control_contracts import PipelineRuntimeControlDraft
from aos_api.pipeline_snapshot_materialization import compile_snapshot_mapping
from aos_api.pipeline_source_selection import MappingReadSpec
from aos_api.pipeline_snapshot_group_owner import PipelineSnapshotGroupOwner
from aos_api.tenant_scope import TenantScope
from aos_api.extension_runtime.lifecycle_store import RuntimeRevisionConflict


def mapping(table):
    spec=MappingReadSpec(table,'Shop','site_id',('site_id','site_name'),(('site_id',1),))
    return compile_snapshot_mapping({'source_table':table,'target_ot':'Shop','primary_key':'site_id','incremental_strategy':'snapshot',
        'site_filter':'site_id=1','field_mappings':[{'source':'site_id','target':'siteId','type':'int'},{'source':'site_name','target':'name','type':'string'}],
        'validation':{'required':['site_id','site_name']},'unique_key_pattern':'niushop:1:{pk}',
        'snapshot_materialization':{'schema_version':'aos.snapshot-materialization/v1','platform':'niushop','shop_key':'site_id','source_timezone':'+08:00','property_defaults':{}}},spec)


@pytest.fixture
def group_case(control_case):
    conn,controls,first,selections,selection,_=control_case
    maps={first.pipeline_id:mapping('ns_site'),'P02-group':mapping('ns_other')}
    def fake_assets(db,item,actor,callback,*,snapshot=False):
        plan=maps[item.pipeline_id]
        return callback(plan if snapshot else plan.read_spec)
    selections._guarded=fake_assets
    first_ref=append(conn,controls,first)
    second_selection=selection.model_copy(update={'pipeline_id':'P02-group'})
    second_ref=approve(conn,selections,second_selection,'group-second-selection')
    body=second_selection.model_dump(exclude={'schema_version'});body['source_selection_ref']=second_ref
    second=PipelineRuntimeControlDraft.model_validate(body)
    second_control=append(conn,controls,second,'group-second-control')
    return conn,PipelineSnapshotGroupOwner(controls=controls),TenantScope(first.org_id,first.project_id),(first_ref,second_control),controls,first


def test_two_real_current_ledgers_consumed_in_same_outer_transaction(group_case):
    conn,owner,scope,refs,_,_=group_case;seen=[]
    with conn.transaction():
        assert owner.run_current(conn,scope=scope,refs=refs,actor='test-actor',execute=lambda group:seen.append(group) or 'done')=='done'
    assert len(seen)==1 and len(seen[0].members)==2
    assert conn.execute('SELECT count(*) FROM pipeline_runtime_control_revision').fetchone()==(2,)


def test_control_superseded_inside_callback_rolls_back_outer_work(group_case):
    conn,owner,scope,refs,controls,first=group_case
    def execute(group):
        controls.append(conn,draft=first,actor='test-actor',idempotency_key='during-group',previous_ref=refs[0])
        return 'must-not-escape'
    with pytest.raises(RuntimeRevisionConflict),conn.transaction():
        owner.run_current(conn,scope=scope,refs=refs,actor='test-actor',execute=execute)
    assert conn.execute('SELECT count(*) FROM pipeline_runtime_control_revision').fetchone()==(2,)
