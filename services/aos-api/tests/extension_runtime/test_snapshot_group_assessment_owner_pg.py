"""Original PG inputs and controls, explicit signed-policy fixture, no source re-read."""
from dataclasses import replace
import hashlib
import json
from types import SimpleNamespace as NS
import pytest
from test_lifecycle_pg import database,pytestmark
from test_pipeline_source_selection_schema_pg import ledger
from test_pipeline_source_selection_owner_pg import owner_case,approve
from test_pipeline_runtime_control_owner_pg import append
from test_pipeline_source_claim_owner_pg import claim_case
from test_controlled_snapshot_ingress_pg import executor_case
from test_snapshot_group_claim_owner_pg import group_claim_case
from test_controlled_snapshot_group_ingress_pg import prepared_case
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef,PipelineSourceSelectionDraft
from aos_api.pipeline_snapshot_group_assessment_owner import PipelineSnapshotGroupAssessmentOwner,_outputs_by_pipeline

@pytest.fixture
def assessment_case(prepared_case):
    executor,conn,args,state=prepared_case;selections=executor._claims._controls._selections;old=selections._guarded
    with conn.transaction():
        second=executor._claims._controls.run_current_snapshot(conn,scope=args['scope'],ref=args['bindings'][1][0],actor=args['actor'],execute=lambda draft,plan:draft)
    def assets(db,item,actor,callback,*,snapshot=False):
        def adapt(plan):
            if item.pipeline_id=='P02-group':plan=replace(plan,read_spec=replace(plan.read_spec,object_type='Weapp'),defaults=plan.defaults+(('appId','fixture-app'),))
            return callback(plan if snapshot else plan.read_spec)
        return old(db,item,actor,adapt,snapshot=True)
    selections._guarded=assets
    changed=second.model_copy(update={'mapping_ref':second.mapping_ref.model_copy(update={'content_hash':'sha256:'+'e'*64})})
    selection=PipelineSourceSelectionDraft.model_validate(changed.model_dump(exclude={'schema_version','source_selection_ref'}))
    selected_ref=approve(conn,selections,selection,'assessment-weapp-selection',second.source_selection_ref)
    control_ref=append(conn,executor._claims._controls,changed.model_copy(update={'source_selection_ref':selected_ref}),'assessment-weapp-control',args['bindings'][1][0])
    args=args|{'bindings':(args['bindings'][0],(control_ref,args['bindings'][1][1]))}
    with conn.transaction():
        draft=executor._claims._controls.run_current_snapshot(conn,scope=args['scope'],ref=args['bindings'][0][0],actor=args['actor'],execute=lambda draft,plan:draft)
    package=draft.package_ref
    selected=NS(publisher=package.publisher,id=package.id,version=package.version,content_hash=package.content_hash,signature_fingerprint='fixture',release_evidence_revision=1)
    document={'schemaVersion':'aos.snapshot-relationships/v1','objectTypes':['Shop','Weapp'],'rules':[dict(linkType='Shop.hasWeapp',rowType='Weapp',parentType='Shop',referenceProperty='siteId',direction='parent-to-row',encoding='positive-id',allowUnset=False)]}
    state['policy_raw']=json.dumps(document).encode()
    selections._store=NS(load_active_baseline_in_transaction=lambda *a,**kw:NS(lock=NS(payload=NS(resolved=[selected]))))
    selections._artifacts=NS(scope=args['scope'],load_record=lambda *a:NS(manifest=NS(spec=NS(exports=NS(policies=['content/policies/'])))),read_artifact=lambda *a:state['policy_raw'])
    def evaluate(*a,**kw):
        if state.get('policy_denied'):raise PermissionError('fixture policy denied')
    selections._release_policy=NS(evaluate=evaluate)
    ref=PipelineExactRef(resource_type='SnapshotRelationshipPolicy',resource_id='content/policies/fixture.json',revision=package.version,content_hash='sha256:'+hashlib.sha256(state['policy_raw']).hexdigest())
    return executor,conn,args,state,PipelineSnapshotGroupAssessmentOwner(claims=executor._claims),ref

@pytest.mark.parametrize('empty',[False,True])
def test_current_policy_and_original_inputs_yield_stable_bound_assessment(assessment_case,empty):
    executor,conn,args,state,owner,ref=assessment_case;state['empty']=empty
    prepared=executor.prepare(**args)
    with conn.transaction():first=owner.run_current(conn,**args,policy_ref=ref,execute=lambda value:value)
    with conn.transaction():again=owner.run_current(conn,**args,policy_ref=ref,execute=lambda value:value)
    assert first==again and first.content_hash.startswith('sha256:')
    assert first.input.manifest_hash==prepared.manifest_hash and first.policy_ref==ref
    assert len(first.assessment.candidate_links)==(0 if empty else 1) and state['calls']==1


def test_original_parents_join_by_pipeline_not_control_family_order(assessment_case):
    executor,conn,args,state,owner,ref=assessment_case;executor.prepare(**args)
    with conn.transaction():current=owner.run_current(conn,**args,policy_ref=ref,execute=lambda value:value)
    outputs=_outputs_by_pipeline(current.input.group,tuple(reversed(current.input.parents)))
    assert set(outputs)=={'Shop','Weapp'}
    assert all(all(row['ot']==object_type for row in rows) for object_type,rows in outputs.items())
    with pytest.raises(ValueError,match='parent pipelines'):
        _outputs_by_pipeline(current.input.group,current.input.parents[:-1])
    assert state['calls']==1


def test_missing_input_does_not_initiate_source(assessment_case):
    _,conn,args,state,owner,ref=assessment_case
    with pytest.raises((LookupError,RuntimeError)),conn.transaction():owner.run_current(conn,**args,policy_ref=ref,execute=lambda v:pytest.fail('missing input'))
    assert state['calls']==0

@pytest.mark.parametrize('fault',['counts','links','input','policy'])
def test_mutated_or_denied_assessment_cannot_escape(assessment_case,fault):
    executor,conn,args,state,owner,ref=assessment_case;executor.prepare(**args)
    def consume(current):
        if fault=='counts':current.assessment.counts['Shop.hasWeapp']['matched']=999
        elif fault=='links':current.assessment.candidate_links[0]['target_source_pk']='999'
        elif fault=='input':current.input.parents[0]['outputRows'].clear()
        else:state['policy_denied']=True
    with pytest.raises((ValueError,RuntimeError,PermissionError)),conn.transaction():owner.run_current(conn,**args,policy_ref=ref,execute=consume)
    assert state['calls']==1
