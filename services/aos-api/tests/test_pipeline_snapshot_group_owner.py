"""Group composition tests with an explicitly doubled current-control gate."""
from datetime import timedelta
from types import SimpleNamespace
from psycopg.pq import TransactionStatus
import pytest
from tests.test_pipeline_runtime_control_contracts import payload
from aos_api.pipeline_runtime_control_contracts import PipelineRuntimeControlDraft,PipelineExactRef
from aos_api.pipeline_runtime_control_owner import PipelineRuntimeControlOwner
from aos_api.pipeline_snapshot_materialization import compile_snapshot_mapping
from aos_api.pipeline_source_selection import MappingReadSpec
from aos_api.pipeline_snapshot_group_owner import PipelineSnapshotGroupOwner
from aos_api.tenant_scope import TenantScope


def compiled(table):
    spec=MappingReadSpec(table,'Shop','id',('id','site_id'),(('site_id',1),))
    return compile_snapshot_mapping({'source_table':table,'target_ot':'Shop','primary_key':'id','incremental_strategy':'snapshot',
        'site_filter':'site_id=1','field_mappings':[{'source':'id','target':'id','type':'int'},{'source':'site_id','target':'siteId','type':'int'}],
        'validation':{'required':['id','site_id']},'unique_key_pattern':'niushop:1:{pk}',
        'snapshot_materialization':{'schema_version':'aos.snapshot-materialization/v1','platform':'niushop','shop_key':'site_id','source_timezone':'+08:00','property_defaults':{}}},spec)


@pytest.fixture
def case():
    first=PipelineRuntimeControlDraft.model_validate(payload());second=first.model_copy(update={'pipeline_id':'P02-group','row_limit':50})
    refs=tuple(PipelineExactRef(resource_type='PipelineRuntimeControlRevision',resource_id='pipeline-control-'+str(i)*8+'-'+str(i)*4+'-'+str(i)*4+'-'+str(i)*4+'-'+str(i)*12,revision=1,content_hash='sha256:'+str(i)*64) for i in (1,2))
    state={'now':first.not_before+timedelta(seconds=1),'calls':[],'drafts':[first,second],'maps':[compiled('table_a'),compiled('table_b')]}
    controls=object.__new__(PipelineRuntimeControlOwner)
    def current(conn,*,scope,ref,actor,execute):
        state['calls'].append(ref.resource_id)
        i=refs.index(ref)
        if state.get('deny')==i:raise PermissionError('fixture current denial')
        return execute(state['drafts'][i],state['maps'][i])
    controls.run_current_snapshot=current
    conn=SimpleNamespace(info=SimpleNamespace(transaction_status=TransactionStatus.INTRANS),execute=lambda *a,**kw:SimpleNamespace(fetchone=lambda:{'now':state['now']}))
    return PipelineSnapshotGroupOwner(controls=controls),conn,TenantScope(first.org_id,first.project_id),refs,state


def test_group_calls_consumer_once_and_revalidates_all_controls(case):
    owner,conn,scope,refs,state=case;seen=[]
    result=owner.run_current(conn,scope=scope,refs=tuple(reversed(refs)),actor='test-actor',execute=lambda group:seen.append(group) or 'done')
    assert result=='done' and len(seen)==1
    assert seen[0].row_limit==50
    assert state['calls']==[r.resource_id for r in refs]*2


@pytest.mark.parametrize('fault',['source','generation','pipeline','table','deny','duplicates','window','tenant'])
def test_mixed_or_invalid_group_never_reaches_consumer(case,fault):
    owner,conn,scope,refs,state=case
    if fault=='source':state['drafts'][1]=state['drafts'][1].model_copy(update={'source_id':'other'})
    elif fault=='generation':state['drafts'][1]=state['drafts'][1].model_copy(update={'generation':'33333333-3333-4333-8333-333333333333'})
    elif fault=='pipeline':state['drafts'][1]=state['drafts'][1].model_copy(update={'pipeline_id':state['drafts'][0].pipeline_id})
    elif fault=='table':state['maps'][1]=state['maps'][0]
    elif fault=='deny':state['deny']=1
    elif fault=='duplicates':refs=(refs[0],refs[0])
    elif fault=='window':state['now']=state['drafts'][0].expires_at
    else:state['drafts'][1]=state['drafts'][1].model_copy(update={'org_id':'dev-org'})
    with pytest.raises((ValueError,PermissionError)):
        owner.run_current(conn,scope=scope,refs=refs,actor='test-actor',execute=lambda group:pytest.fail('invalid group executed'))


@pytest.mark.parametrize('fault',['drift','expired','deferred'])
def test_changed_or_deferred_consumer_result_is_rejected(case,fault):
    owner,conn,scope,refs,state=case
    def execute(group):
        if fault=='drift':state['drafts'][1]=state['drafts'][1].model_copy(update={'row_limit':49})
        elif fault=='expired':state['now']=state['drafts'][0].expires_at
        else:return (item for item in [1])
        return 'uncommitted'
    with pytest.raises((ValueError,PermissionError,TypeError)):
        owner.run_current(conn,scope=scope,refs=refs,actor='test-actor',execute=execute)
