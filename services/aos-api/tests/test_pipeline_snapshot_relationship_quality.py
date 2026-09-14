from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from aos_api.pipeline_snapshot_relationships import compile_relationship_policy
from aos_api.pipeline_snapshot_relationship_quality import (
    compile_relationship_quality_policy, measure_relationship_quality,
)

NOW = datetime(2026, 9, 14, tzinfo=timezone.utc)


def fixture(encoding='positive-id', allow_unset=False, direction='row-to-parent'):
    name = 'Order.customer' if direction == 'row-to-parent' else 'Customer.orders'
    relation = compile_relationship_policy(dict(schemaVersion='aos.snapshot-relationships/v1',
        objectTypes=['Order', 'Customer'], rules=[dict(linkType=name, rowType='Order',
        parentType='Customer', referenceProperty='customer', direction=direction,
        encoding=encoding, allowUnset=allow_unset)]))
    # A second required rule ensures disclosure cannot be the entire purpose.
    document = dict(schemaVersion='aos.snapshot-relationships/v1', objectTypes=['Order', 'Customer'],
        rules=[dict(linkType=r.link_type, rowType=r.row_type, parentType=r.parent_type,
            referenceProperty=r.reference_property, direction=r.direction,
            encoding=r.encoding, allowUnset=r.allow_unset) for r in relation.rules])
    document['rules'].append(dict(linkType='Order.owner', rowType='Order', parentType='Customer',
        referenceProperty='owner', direction='row-to-parent', encoding='positive-id', allowUnset=False))
    relation = compile_relationship_policy(document)
    usage = dict(schemaVersion='aos.snapshot-relationship-quality/v1', relationshipPolicyHash=relation.content_hash,
        purposes=[dict(purposeCode='store_analysis', rules=[dict(linkType=name, requirement='disclose'),
            dict(linkType='Order.owner', requirement='required')]),
            dict(purposeCode='customer_analysis', rules=[dict(linkType=name, requirement='required'),
                dict(linkType='Order.owner', requirement='required')])])
    return relation, usage, name


def row(ot, key, deleted=False, **properties):
    return dict(ot=ot, source_pk=str(key), is_deleted=deleted, properties=properties)


def measure(outputs, *, encoding='positive-id', allow_unset=False, direction='row-to-parent'):
    relation, document, name = fixture(encoding, allow_unset, direction)
    usage = compile_relationship_quality_policy(document, relationship_policy=relation)
    result = measure_relationship_quality(outputs, relation, usage, observed_at=NOW)
    return result, name


def test_missing_customer_preserves_real_order_denominator_and_disclosure():
    outputs = dict(Order=[row('Order', i, customer=1 if i <= 98 else 9, owner=1) for i in range(1, 126)]
        + [row('Order', 200+i, True, customer=9, owner=1) for i in range(60)],
        Customer=[row('Customer', 1)])
    before = deepcopy(outputs)
    result, name = measure(outputs)
    counts = result.counts[name]
    assert counts == dict(observedRows=185, excludedRows=60, eligibleRows=125,
        completeRows=98, allowedUnsetRows=0, incompleteRows=27, missingReferenceRows=0,
        invalidReferenceRows=0, missingParentRows=27, deletedParentRows=0)
    assert result.purposes['store_analysis']['disclosedIncomplete'] == (name,)
    assert result.purposes['store_analysis']['requiredIncomplete'] == ()
    assert result.purposes['customer_analysis']['requiredIncomplete'] == (name,)
    assert not hasattr(result, 'satisfied') and not hasattr(result, 'ready')
    assert outputs == before


def test_multireference_row_complete_only_if_every_parent_present_and_active():
    outputs = dict(Order=[row('Order', 1, customer=',1,2,', owner=1),
        row('Order', 2, customer=',1,3,', owner=1), row('Order', 3, customer=',2,3,', owner=1),
        row('Order', 4, customer=',1,', owner=1)],
        Customer=[row('Customer', 1), row('Customer', 2, True)])
    result, name = measure(outputs, encoding='wrapped-csv-positive-id')
    c = result.counts[name]
    assert (c['eligibleRows'], c['completeRows'], c['incompleteRows']) == (4, 1, 3)
    assert (c['missingParentRows'], c['deletedParentRows']) == (2, 2)


@pytest.mark.parametrize('direction', ['row-to-parent', 'parent-to-row'])
def test_reference_shape_and_unset_are_separate_from_complete_rows(direction):
    outputs = dict(Order=[row('Order', i+1, customer=v, owner=1)
        for i, v in enumerate([None, True, '01', 0, '0', '', 1])], Customer=[row('Customer', 1)])
    result, name = measure(outputs, allow_unset=True, direction=direction)
    c = result.counts[name]
    assert (c['completeRows'], c['allowedUnsetRows'], c['incompleteRows']) == (1, 3, 3)
    assert (c['missingReferenceRows'], c['invalidReferenceRows']) == (1, 2)


def test_empty_table_reports_zero_not_one_success():
    result, name = measure(dict(Order=[], Customer=[]))
    assert set(result.counts[name].values()) == {0}
    assert result.purposes['store_analysis']['emptyRules'] == (name, 'Order.owner')


@pytest.mark.parametrize('mutation', ['hash', 'missing', 'duplicate', 'unknown', 'all_disclose', 'extra', 'purpose'])
def test_policy_must_be_explicit_and_complete(mutation):
    relation, document, _ = fixture()
    rules = document['purposes'][0]['rules']
    if mutation == 'hash': document['relationshipPolicyHash'] = 'sha256:' + '0'*64
    if mutation == 'missing': rules.pop()
    if mutation == 'duplicate': rules.append(deepcopy(rules[0]))
    if mutation == 'unknown': rules[0]['linkType'] = 'Order.unknown'
    if mutation == 'all_disclose': rules[1]['requirement'] = 'disclose'
    if mutation == 'extra': document['ready'] = True
    if mutation == 'purpose': document['purposes'][1]['purposeCode'] = 'store_analysis'
    with pytest.raises(ValueError): compile_relationship_quality_policy(document, relationship_policy=relation)


def test_compiled_policy_cannot_be_forged():
    relation, document, _ = fixture()
    policy = compile_relationship_quality_policy(document, relationship_policy=relation)
    with pytest.raises(ValueError):
        measure_relationship_quality(dict(Order=[], Customer=[]), relation,
            replace(policy, content_hash='sha256:'+'0'*64), observed_at=NOW)


@pytest.mark.parametrize('mutation', ['duplicate', 'missing_type', 'deleted_bool', 'identity', 'naive'])
def test_original_cohort_guards_remain(mutation):
    relation, document, _ = fixture()
    policy = compile_relationship_quality_policy(document, relationship_policy=relation)
    outputs = dict(Order=[row('Order', 1, customer=1, owner=1)], Customer=[row('Customer', 1)])
    when = NOW
    if mutation == 'duplicate': outputs['Order'].append(deepcopy(outputs['Order'][0]))
    if mutation == 'missing_type': outputs.pop('Customer')
    if mutation == 'deleted_bool': outputs['Order'][0]['is_deleted'] = 0
    if mutation == 'identity': outputs['Order'][0]['source_pk'] = '01'
    if mutation == 'naive': when = NOW.replace(tzinfo=None)
    with pytest.raises(ValueError): measure_relationship_quality(outputs, relation, policy, observed_at=when)
