"""Drafts bind exact references but never authorize execution."""
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from aos_api.pipeline_runtime_control_contracts import PipelineRuntimeControlDraft


def payload():
    def ref(kind, identity='pinned-reference'):
        return {'resourceType':kind,'resourceId':identity,'revision':1,'contentHash':'sha256:'+'a'*64}
    now=datetime(2026,9,12,tzinfo=timezone.utc)
    return {
        'orgId':'test-org','projectId':'test-project','pipelineId':'P01-shop-qyh',
        'graphRevision':1,'graphHash':'b'*64,
        'installationRef':{'installationId':'11111111-1111-4111-8111-111111111111','revision':5,'lockHash':'sha256:'+'c'*64,'overlayRevision':'1'},
        'generation':'22222222-2222-4222-8222-222222222222','executionEpoch':1,
        'configurationRef':{'configurationId':'33333333-3333-4333-8333-333333333333','revision':1,'hash':'sha256:'+'d'*64},
        'packageRef':{'publisher':'aos','id':'ecommerce-niushop','version':'1.3.0','contentHash':'sha256:'+'e'*64},
        'sourceId':'niushop-qyh',
        'sourceConfigurationRef':ref('DataSourceConfigurationRevision','source-config-44444444-4444-4444-8444-444444444444'),
        'sourceSelectionRef':ref('SourceSelectionRevision'),
        'mappingRef':ref('Mapping'),'schemaRef':ref('SchemaFingerprint'),'maskingPolicyRef':ref('MaskingPolicy'),
        'rowLimit':100,'timeoutSeconds':30,'maxSourceCalls':1,'notBefore':now,'expiresAt':now+timedelta(hours=1),
    }


def test_roundtrip_is_stable_and_never_enabled():
    item=PipelineRuntimeControlDraft.model_validate(payload())
    assert item.state=='prepared' and item.read_only is True
    assert item.content_hash() == 'sha256:9b91cdf86f2ce473c33b8e90f36ccf2c68b58d298fa20c80f70238563668f77b'
    assert PipelineRuntimeControlDraft.model_validate_json(item.model_dump_json(by_alias=True))==item
    assert item.content_hash()==PipelineRuntimeControlDraft.model_validate(payload()).content_hash()
    changed=payload();changed['rowLimit']=50
    assert PipelineRuntimeControlDraft.model_validate(changed).content_hash()!=item.content_hash()


def test_copied_and_nested_references_are_immutable():
    value=payload(); item=PipelineRuntimeControlDraft.model_validate(value)
    value['installationRef']['revision']=99
    assert item.installation_ref.revision==5
    with pytest.raises(ValidationError): item.installation_ref.revision=6
    with pytest.raises(ValidationError): item.source_configuration_ref.revision=2
    with pytest.raises(ValidationError): item.row_limit=1


@pytest.mark.parametrize('key,value',[
    ('enabled',True),('execution_mode','live'),('sql','select * from anything'),
    ('state','active'),('readOnly',False),('readOnly',1),('orgId',' '),('projectId',' project'),
    ('pipelineId',''),('graphRevision',True),('executionEpoch','1'),('graphHash','sha256:'+'b'*64),
    ('rowLimit',0),('rowLimit',1001),('rowLimit',True),('timeoutSeconds',31),
    ('maxSourceCalls',33),('generation','{22222222-2222-4222-8222-222222222222}'),
])
def test_invalid_control_values_are_rejected(key,value):
    body=payload();body[key]=value
    with pytest.raises(ValidationError): PipelineRuntimeControlDraft.model_validate(body)


@pytest.mark.parametrize('field,kind',[
    ('sourceConfigurationRef','SourceConfig'),('sourceSelectionRef','Approval'),
    ('mappingRef','SchemaFingerprint'),('schemaRef','Mapping'),('maskingPolicyRef','Mapping'),
])
def test_reference_purpose_is_exact(field,kind):
    body=payload();body[field]['resourceType']=kind
    with pytest.raises(ValidationError): PipelineRuntimeControlDraft.model_validate(body)


@pytest.mark.parametrize('edit', ['reverse','naive','too_long','source_uuid','source_revision','ref_space','package_range'])
def test_time_and_reference_identity_are_bounded(edit):
    body=payload()
    if edit=='reverse': body['expiresAt']=body['notBefore']
    elif edit=='naive': body['notBefore']=body['notBefore'].replace(tzinfo=None)
    elif edit=='too_long': body['expiresAt']=body['notBefore']+timedelta(days=2)
    elif edit=='source_uuid': body['sourceConfigurationRef']['resourceId']='source-config-not-a-uuid'
    elif edit=='source_revision': body['sourceConfigurationRef']['revision']='1'
    elif edit=='ref_space': body['mappingRef']['resourceId']=' padded '
    else: body['packageRef']['version']='^1.3.0'
    with pytest.raises(ValidationError): PipelineRuntimeControlDraft.model_validate(body)


def test_validation_message_hides_rejected_input():
    body=payload();body['password']='fixture-private-not-to-log'
    with pytest.raises(ValidationError) as err: PipelineRuntimeControlDraft.model_validate(body)
    assert 'fixture-private-not-to-log' not in str(err.value)


def test_revalidation_rejects_constructed_or_copied_invalid_values():
    item=PipelineRuntimeControlDraft.model_validate(payload())
    invalid=item.model_copy(update={'row_limit': True})
    with pytest.raises(ValidationError): invalid.content_hash()


def test_equivalent_timezones_have_same_hash():
    body=payload(); other=payload()
    zone=timezone(timedelta(hours=8))
    other['notBefore']=other['notBefore'].astimezone(zone)
    other['expiresAt']=other['expiresAt'].astimezone(zone)
    assert PipelineRuntimeControlDraft.model_validate(body).content_hash()==PipelineRuntimeControlDraft.model_validate(other).content_hash()


@pytest.mark.parametrize('field,update', [
    ('installation_ref', {'revision': True}),
    ('configuration_ref', {'revision': 0}),
    ('source_configuration_ref', {'content_hash': 'invalid'}),
    ('package_ref', {'version': '^1.3.0'}),
])
def test_nested_unvalidated_copies_cannot_be_hashed(field, update):
    item = PipelineRuntimeControlDraft.model_validate(payload())
    ref = getattr(item, field).model_copy(update=update)
    invalid = item.model_copy(update={field: ref})
    with pytest.raises(ValidationError):
        invalid.content_hash()


def test_source_selection_draft_has_no_self_reference_or_approval():
    from aos_api.pipeline_runtime_control_contracts import PipelineSourceSelectionDraft
    body = payload()
    body.pop('sourceSelectionRef')
    item = PipelineSourceSelectionDraft.model_validate(body)
    assert item.state == 'prepared' and item.read_only is True
    assert 'sourceSelectionRef' not in item.model_dump(by_alias=True)
    assert item.schema_version == 'aos.pipeline-source-selection-draft/v1'
    assert PipelineSourceSelectionDraft.model_validate_json(item.model_dump_json(by_alias=True)) == item
    with pytest.raises(ValidationError):
        PipelineSourceSelectionDraft.model_validate(payload())
    with pytest.raises(ValidationError):
        PipelineSourceSelectionDraft.model_validate({**body, 'state': 'approved'})


@pytest.mark.parametrize('key,value', [('rowLimit', True), ('graphRevision', 0), ('readOnly', False)])
def test_source_selection_inherits_strict_control_bounds(key, value):
    from aos_api.pipeline_runtime_control_contracts import PipelineSourceSelectionDraft
    body = payload()
    body.pop('sourceSelectionRef')
    body[key] = value
    with pytest.raises(ValidationError):
        PipelineSourceSelectionDraft.model_validate(body)
