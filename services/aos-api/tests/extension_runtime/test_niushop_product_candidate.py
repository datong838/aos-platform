from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'bundles/platforms/ecommerce-niushop/backend'))
from ecommerce_niushop.product_candidate import product_candidate_status


def record():
    return dict(identity=dict(org_id='org-a', workspace_id='workspace-a', platform='niushop',
                              shop_or_marketplace_id='1', external_id='niushop:1:7'),
                object_type='Product', is_deleted=False,
                status=dict(canonical_value='active', raw_status='ACTIVE', unknown=False),
                properties=dict(state=1, isDelete=0))


def check(value):
    return product_candidate_status(value, org_id='org-a', project_id='workspace-a', shop_id='1')


def test_active_and_input_immutable():
    value = record()
    before = deepcopy(value)
    assert check(value) == 'ELIGIBLE_STATUS'
    assert value == before


@pytest.mark.parametrize('canonical,unknown', [('unknown', True), ('inactive', False)])
def test_inactive_is_distinct_from_deleted(canonical, unknown):
    value = record()
    value['properties']['state'] = 0
    value['status'] = dict(canonical_value=canonical, raw_status='INACTIVE', unknown=unknown)
    assert check(value) == 'INACTIVE'


def test_deleted_is_not_an_active_candidate():
    value = record()
    value['is_deleted'] = True
    value['properties']['isDelete'] = 1
    value['status'] = dict(canonical_value='deleted', raw_status='DELETED', unknown=False)
    assert check(value) == 'DELETED'


@pytest.mark.parametrize('field,value', [('org_id','other'), ('workspace_id','other'),
    ('shop_or_marketplace_id','2'), ('platform','other'), ('external_id','')])
def test_wrong_identity_is_rejected(field, value):
    item = record()
    item['identity'][field] = value
    assert check(item) == 'INVALID_IDENTITY'


@pytest.mark.parametrize('key,value', [('state', True), ('state', '1'), ('state', None),
    ('isDelete', False), ('isDelete', '0'), ('isDelete', None), ('state', 2), ('isDelete', 2)])
def test_no_coercion_or_unknown_source_values(key, value):
    item = record()
    item['properties'][key] = value
    assert check(item) == 'INVALID_STATE'


@pytest.mark.parametrize('mutation', ['missing', 'unknown', 'raw', 'inactive', 'deleted',
    'not_bool', 'sku', 'no_status', 'no_identity', 'no_properties'])
def test_malformed_or_contradictory_does_not_become_eligible(mutation):
    value = record()
    if mutation == 'missing': del value['properties']['state']
    elif mutation == 'unknown': value['status']['unknown'] = True
    elif mutation == 'raw': value['status']['raw_status'] = 'UNRECOGNIZED'
    elif mutation == 'inactive': value['properties']['state'] = 0
    elif mutation == 'deleted': value['is_deleted'] = True
    elif mutation == 'not_bool': value['is_deleted'] = 0
    elif mutation == 'sku': value['object_type'] = 'ProductSku'
    else: value[mutation.removeprefix('no_')] = None
    assert check(value) != 'ELIGIBLE_STATUS'


@pytest.mark.parametrize('value', [None, [], 'product'])
def test_malformed_record(value):
    assert check(value) == 'INVALID_RECORD'


@pytest.mark.parametrize('scope', [('','workspace-a','1'), ('org-a','','1'), ('org-a','workspace-a','')])
def test_missing_requested_scope_rejected(scope):
    assert product_candidate_status(record(),org_id=scope[0],project_id=scope[1],shop_id=scope[2]) == 'INVALID_IDENTITY'
