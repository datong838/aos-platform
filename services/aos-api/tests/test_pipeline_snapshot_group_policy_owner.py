"""Current group composition with explicit installation/artifact/release doubles."""
from dataclasses import replace
import hashlib
import json
from types import SimpleNamespace as NS
import pytest
from tests.test_pipeline_snapshot_group_owner import case
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_snapshot_group_policy_owner import PipelineSnapshotGroupPolicyOwner

@pytest.fixture
def bound(case):
    owner,conn,scope,refs,state=case
    state['maps']=[replace(m,read_spec=replace(m.read_spec,object_type=ot)) for m,ot in zip(state['maps'],['Order','OrderLine'])]
    doc={'schemaVersion':'aos.snapshot-relationships/v1','objectTypes':['Order','OrderLine'],'rules':[dict(linkType='Order.lines',rowType='OrderLine',parentType='Order',referenceProperty='siteId',direction='parent-to-row',encoding='positive-id',allowUnset=False)]}
    state['raw']=json.dumps(doc).encode();state['doc']=doc;state['release_calls']=0
    draft=state['drafts'][0];package=draft.package_ref
    selected=NS(publisher=package.publisher,id=package.id,version=package.version,content_hash=package.content_hash,signature_fingerprint='fixture',release_evidence_revision=1)
    state['resolved']=[selected];state['exports']=['content/policies/']
    store=NS(load_active_baseline_in_transaction=lambda *a,**kw:NS(lock=NS(payload=NS(resolved=state['resolved']))))
    def evaluate(record,**kwargs):
        state['release_calls']+=1
        assert kwargs['expected_signature_fingerprint']=='fixture' and kwargs['expected_evidence_revision']==1
        if state.get('release_denied'):raise PermissionError('fixture release denied')
    artifacts=NS(scope=scope,load_record=lambda selected:NS(manifest=NS(spec=NS(exports=NS(policies=state['exports'])))),read_artifact=lambda *args:state['raw'])
    selections=NS(_store=store,_artifacts=artifacts,_release_policy=NS(evaluate=evaluate))
    owner._controls._selections=selections
    policy_ref=PipelineExactRef(resource_type='SnapshotRelationshipPolicy',resource_id='content/policies/snapshot-relationships.v1.json',revision=package.version,content_hash='sha256:'+hashlib.sha256(state['raw']).hexdigest())
    args=dict(scope=scope,refs=refs,actor='fixture',policy_ref=policy_ref)
    return PipelineSnapshotGroupPolicyOwner(controls=owner._controls),conn,args,state,selections


def test_current_exported_policy_checked_before_and_after_callback(bound):
    owner,conn,args,state,_=bound;seen=[]
    result=owner.run_current(conn,**args,execute=lambda current:seen.append(current) or 'done')
    assert result=='done' and len(seen)==1 and state['release_calls']==2
    assert seen[0].policy.object_types==('Order','OrderLine')
    assert seen[0].policy_ref==args['policy_ref']

@pytest.mark.parametrize('fault',['tenant','package','exports','version','hash','traversal','resource_type','release','duplicate_json','missing_type','missing_field'])
def test_invalid_current_asset_never_consumed(bound,fault):
    owner,conn,args,state,selections=bound
    if fault=='tenant':selections._artifacts.scope=NS(key=('other','other'))
    elif fault=='package':state['resolved']=[]
    elif fault=='exports':state['exports']=[]
    elif fault=='version':args['policy_ref']=args['policy_ref'].model_copy(update={'revision':'9.9.9'})
    elif fault=='hash':state['raw']+=b' '
    elif fault=='traversal':args['policy_ref']=args['policy_ref'].model_copy(update={'resource_id':'content/policies/../secret.json'})
    elif fault=='resource_type':args['policy_ref']=args['policy_ref'].model_copy(update={'resource_type':'Other'})
    elif fault=='release':state['release_denied']=True
    else:
        if fault=='duplicate_json':state['raw']=b'{"schemaVersion":1,"schemaVersion":2}'
        else:
            if fault=='missing_type':state['doc']['objectTypes']+=['Shop']
            else:state['doc']['rules'][0]['referenceProperty']='unmapped'
            state['raw']=json.dumps(state['doc']).encode()
        args['policy_ref']=args['policy_ref'].model_copy(update={'content_hash':'sha256:'+hashlib.sha256(state['raw']).hexdigest()})
    with pytest.raises((ValueError,PermissionError)):
        owner.run_current(conn,**args,execute=lambda current:pytest.fail('invalid policy consumed'))

@pytest.mark.parametrize('fault',['artifact','release','deferred'])
def test_callback_cannot_escape_current_policy(bound,fault):
    owner,conn,args,state,_=bound
    def consume(current):
        if fault=='artifact':state['raw']+=b' '
        elif fault=='release':state['release_denied']=True
        else:return (x for x in [1])
        return 'uncommitted'
    with pytest.raises((ValueError,PermissionError,TypeError)):owner.run_current(conn,**args,execute=consume)


def test_public_projection_hides_underlying_reference_field(bound):
    from aos_api.pipeline_snapshot_materialization_v3 import SnapshotMappingV3
    owner,conn,args,state,_=bound
    state['maps'][1]=SnapshotMappingV3(base=state['maps'][1],conversions=(),non_negative=(),status_field='site_id',status_target='status',statuses=((1,'ACTIVE'),),public_projection=(2,('status',)))
    with pytest.raises(ValueError,match='public output'):
        owner.run_current(conn,**args,execute=lambda current:pytest.fail('hidden field used'))
