from datetime import timedelta

import pytest
from pydantic import ValidationError

from test_pipeline_runtime_control_contracts import payload as pipeline_payload
from aos_api.pipeline_runtime_control_contracts import PipelineSourceSelectionDraft, PipelineExactRef
from aos_api.pipeline_source_selection_store import SourceSelectionRecord
from aos_api.pipeline_source_selection import MappingReadSpec
from aos_api.ecommerce_product_event_policy import ProductEventPolicyDraft


def case():
    source = pipeline_payload()
    selection_ref = source.pop('sourceSelectionRef')
    draft = PipelineSourceSelectionDraft.model_validate(source)
    spec = MappingReadSpec('ns_goods', 'Product', 'goods_id', ('goods_id',), (('site_id', 1),))
    record = SourceSelectionRecord(PipelineExactRef.model_validate(selection_ref), draft, spec, 'fixture', None)
    body = {key: source[key] for key in ('orgId', 'projectId', 'installationRef', 'generation',
        'executionEpoch', 'configurationRef', 'sourceConfigurationRef')}
    body.update(policyId='product-method', sourceSelectionRef=selection_ref,
        platform='niushop', shopOrMarketplaceId='1', objectTypes=('Product',),
        methodVersion='aos.product-source-event/v1', effectiveFrom=source['notBefore'],
        effectiveUntil=source['expiresAt'], maxSourceAgeSeconds=3600, recoveryWindowSeconds=600)
    return body, record


def test_roundtrip_hash_and_selection_binding():
    body, selection = case()
    policy = ProductEventPolicyDraft.model_validate(body)
    policy.validate_selection(selection)
    assert ProductEventPolicyDraft.model_validate_json(policy.model_dump_json(by_alias=True)) == policy
    changed = dict(body, recoveryWindowSeconds=300)
    assert ProductEventPolicyDraft.model_validate(changed).content_hash() != policy.content_hash()
    with pytest.raises(ValidationError):
        policy.policy_id = 'changed'


@pytest.mark.parametrize('key,value', [('approved', True), ('enabled', True), ('sql', 'select 1'),
    ('objectTypes', ()), ('objectTypes', ('Product', 'Product')), ('objectTypes', ('Order',)),
    ('recoveryWindowSeconds', True), ('maxSourceAgeSeconds', 86401), ('recoveryWindowSeconds', 0),
    ('platform', ' niushop'), ('shopOrMarketplaceId', ''), ('executionEpoch', True),
    ('generation', 'invalid'), ('methodVersion', 'snapshot')])
def test_invalid_or_self_authorizing_inputs_rejected(key, value):
    body, _ = case(); body[key] = value
    with pytest.raises(ValidationError): ProductEventPolicyDraft.model_validate(body)


@pytest.mark.parametrize('key,value', [('orgId', 'other-org'), ('generation', '55555555-5555-4555-8555-555555555555'),
    ('executionEpoch', 2)])
def test_selection_scope_drift_rejected(key, value):
    body, selection = case(); body[key] = value
    with pytest.raises(ValueError): ProductEventPolicyDraft.model_validate(body).validate_selection(selection)


@pytest.mark.parametrize('key', ['sourceSelectionRef', 'sourceConfigurationRef', 'configurationRef', 'installationRef'])
def test_exact_reference_drift_rejected(key):
    body, selection = case(); body[key] = {**body[key], 'revision': 2}
    with pytest.raises(ValueError): ProductEventPolicyDraft.model_validate(body).validate_selection(selection)


def test_windows_do_not_extend_selection_and_copied_models_are_revalidated():
    body, selection = case()
    policy = ProductEventPolicyDraft.model_validate(body)
    copied = policy.model_copy(update={'recovery_window_seconds': True})
    with pytest.raises(ValidationError): copied.content_hash()
    with pytest.raises(ValidationError): copied.validate_selection(selection)
    body['effectiveUntil'] += timedelta(minutes=1)
    with pytest.raises(ValueError): ProductEventPolicyDraft.model_validate(body).validate_selection(selection)
    body['effectiveUntil'] = body['effectiveFrom'] + timedelta(days=2)
    with pytest.raises(ValidationError): ProductEventPolicyDraft.model_validate(body)


def test_selection_cannot_expand_to_a_second_object_type():
    body, selection = case()
    body['objectTypes'] = ('Product', 'ProductSku')
    with pytest.raises(ValueError, match='selected mapping'):
        ProductEventPolicyDraft.model_validate(body).validate_selection(selection)
