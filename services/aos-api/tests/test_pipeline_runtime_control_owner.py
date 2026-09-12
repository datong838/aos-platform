from copy import deepcopy
from uuid import uuid4
import pytest
from aos_api.pipeline_runtime_control_contracts import PipelineRuntimeControlDraft, PipelineSourceSelectionDraft
from aos_api.pipeline_runtime_control_owner import verify_control_selection, build_control_payload, decode_control_row, control_request_hash
from aos_api.asset_registry.canonical_json import canonical_sha256
from tests.test_pipeline_runtime_control_contracts import payload


def drafts():
    body=payload();body['sourceSelectionRef']['resourceId']='source-selection-'+str(uuid4())
    control=PipelineRuntimeControlDraft.model_validate(body)
    body.pop('sourceSelectionRef')
    return control,PipelineSourceSelectionDraft.model_validate(body)


def test_shared_selection_context_is_exact():
    control,selection=drafts()
    verify_control_selection(control,selection)
    for field,value in [('row_limit',101),('graph_revision',2),('source_id','another'),('max_source_calls',2)]:
        with pytest.raises(ValueError):verify_control_selection(control.model_copy(update={field:value}),selection)


def row_case():
    draft,_=drafts();identity=str(uuid4())
    args=dict(draft=draft,control_id=identity,revision=1,previous_hash=None,actor='actor')
    body=build_control_payload(**args)
    row={key:body[name] for key,name in [('org_id','orgId'),('project_id','projectId'),('installation_id','installationId'),('generation','generation'),('pipeline_id','pipelineId'),('control_id','controlId'),('revision','revision'),('selection_id','selectionId'),('selection_revision','selectionRevision'),('selection_hash','selectionHash'),('actor','actor')]}
    row.update(payload=body,content_hash=canonical_sha256(body),previous_revision=None,previous_hash=None,request_hash=control_request_hash(**args))
    return row,args


def test_control_record_roundtrip_and_request_identity():
    row,args=row_case()
    saved=decode_control_row(row)
    assert saved.draft==args['draft'] and saved.ref.resource_type=='PipelineRuntimeControlRevision'
    assert control_request_hash(**(args|dict(control_id=str(uuid4()))))==row['request_hash']


@pytest.mark.parametrize('mode',['payload','column','hash','request','previous','selection_hash'])
def test_control_record_tampering_is_rejected(mode):
    row,_=row_case()
    if mode=='payload':row['payload']['draft']['rowLimit']=999
    elif mode=='column':row['pipeline_id']='other'
    elif mode=='hash':row['content_hash']='sha256:'+'f'*64
    elif mode=='request':row['request_hash']='sha256:'+'f'*64
    elif mode=='previous':row['previous_revision']=0
    else:row['selection_hash']='sha256:'+'f'*64
    with pytest.raises(ValueError):decode_control_row(row)


def test_control_boolean_header_cannot_equal_integer_revision():
    row,_=row_case()
    row['payload']['revision']=True
    with pytest.raises(ValueError):decode_control_row(row)
