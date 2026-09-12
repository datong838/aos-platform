"""Verified asset interpretation, not live source or permission acceptance."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path

import pytest
import yaml

from aos_api.pipeline_source_selection import derive_mapping_read_spec


def assets():
    root = Path(__file__).resolve().parents[3] / 'bundles/platforms/ecommerce-niushop/content'
    return (
        yaml.safe_load((root / 'mappings/p01-shop.yaml').read_text()),
        json.loads((root / 'schemas/niushop-schema-fingerprint.json').read_text()),
        yaml.safe_load((root / 'mappings/_pii-exclusion.yaml').read_text()),
    )


def test_real_p01_asset_shape_yields_only_scoped_non_pii_columns():
    mapping, schema, policy = assets()
    result = derive_mapping_read_spec(mapping, schema, policy)
    assert result.table == 'ns_site'
    assert result.object_type == 'Shop'
    assert result.primary_key == 'site_id'
    assert result.filters == (('site_id', 1),)
    assert len(result.columns) == 11 and 'site_tel' not in result.columns
    mapping['field_mappings'][0]['source'] = 'mutated'
    assert result.columns[0] == 'site_id'
    with pytest.raises(FrozenInstanceError):
        result.table = 'another_table'


@pytest.mark.parametrize('case', [
    'empty_columns', 'duplicate_columns', 'unsafe_column', 'missing_pk', 'unsafe_table',
    'missing_filter', 'unsafe_filter', 'missing_policy', 'direct_pii', 'quasi_pii',
    'masked_field', 'global_drop', 'schema_duplicate', 'schema_pk', 'schema_type',
    'schema_pipeline', 'incremental', 'too_many_columns', 'policy_wrong_shape',
    'pii_uppercase', 'duplicate_case',
])
def test_inconsistent_or_unbounded_assets_are_rejected(case):
    mapping, schema, policy = assets()
    if case == 'empty_columns': mapping['field_mappings'] = []
    elif case == 'duplicate_columns': mapping['field_mappings'].append(deepcopy(mapping['field_mappings'][0]))
    elif case == 'unsafe_column': mapping['field_mappings'][0]['source'] = '*'
    elif case == 'missing_pk': mapping['field_mappings'] = mapping['field_mappings'][1:]
    elif case == 'unsafe_table': mapping['source_table'] = 'ns_site; SELECT 1'
    elif case == 'missing_filter': mapping.pop('site_filter')
    elif case == 'unsafe_filter': mapping['site_filter'] = 'site_id=1 OR 1=1'
    elif case == 'missing_policy': policy['tables'].pop('ns_site')
    elif case == 'direct_pii': mapping['field_mappings'].append({'source': 'site_tel', 'target': 'telephone'})
    elif case == 'quasi_pii': policy['tables']['ns_site']['pii_quasi'] = ['site_name']
    elif case == 'masked_field': policy['tables']['ns_site']['sensitive_mask'] = ['site_name']
    elif case == 'global_drop': policy['global_drop_on_project_node'].append('site_name')
    elif case == 'schema_duplicate': schema['tables'].append(deepcopy(schema['tables'][0]))
    elif case == 'schema_pk': schema['tables'][0]['primaryKey'] = 'another_id'
    elif case == 'schema_type': schema['tables'][0]['targetOt'] = 'Product'
    elif case == 'schema_pipeline': schema['tables'][0]['pipelineId'] = 'P02'
    elif case == 'incremental': mapping['incremental_strategy'] = 'incremental'
    elif case == 'too_many_columns': mapping['field_mappings'] += [{'source': f'column_{i}'} for i in range(100)]
    elif case == 'pii_uppercase': mapping['field_mappings'].append({'source': 'SITE_TEL'})
    elif case == 'duplicate_case': mapping['field_mappings'].append({'source': 'SITE_ID'})
    else: policy['tables']['ns_site']['pii_direct'] = 'site_tel'
    with pytest.raises(ValueError):
        derive_mapping_read_spec(mapping, schema, policy)
