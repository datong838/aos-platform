from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml
from aos_api.pipeline_source_selection import MappingReadSpec
from aos_api.pipeline_snapshot_materialization import compile_snapshot_mapping, materialize_snapshot


def mapping():
    root=Path(__file__).resolve().parents[3]
    value=yaml.safe_load((root/'bundles/candidates/ecommerce/platform.ecommerce.niushop/1.3.0/content/mappings/p01-shop.yaml').read_text())
    value['snapshot_materialization']={'schema_version':'aos.snapshot-materialization/v1','platform':'niushop','shop_key':'site_id',
        'source_timezone':'+08:00','property_defaults':{'status':'active','currency':'CNY','timezone':'+08:00'}}
    return value


def compiled(value=None):
    value=value or mapping()
    spec=MappingReadSpec('ns_site','Shop','site_id',tuple(field['source'] for field in mapping()['field_mappings']),(('site_id',1),))
    return compile_snapshot_mapping(value,spec)


def row():
    value={item['source']:'' for item in mapping()['field_mappings']}
    value.update(site_id=1,site_name='测试店铺',create_time=0)
    return value

NOW=datetime(2026,9,12,12,tzinfo=timezone.utc)


def test_all_declared_fields_and_defaults_materialize_without_raw_extras():
    plan=compiled();raw=row();original=deepcopy(raw)
    result=materialize_snapshot([raw],plan,observed_at=NOW)
    assert plan.platform=='niushop' and plan.shop_id=='1'
    assert result[0]['external_id']=='niushop:1:1'
    assert result[0]['source_updated_at']==NOW
    assert result[0]['properties']['createTime'] is None
    assert result[0]['properties']['siteId']==1
    assert result[0]['properties']['name']=='测试店铺'
    assert len(result[0]['properties'])==14
    assert set(result[0])=={'ot','source_pk','external_id','source_updated_at','source_timezone','is_deleted','properties'}
    assert raw==original
    assert materialize_snapshot([raw],plan,observed_at=NOW)==result


def test_source_time_is_distinct_from_snapshot_observation():
    raw=row();raw['create_time']=1
    result=materialize_snapshot([raw],compiled(),observed_at=NOW)[0]
    assert result['properties']['createTime']=='1970-01-01T00:00:01Z'
    assert result['source_updated_at']==NOW


@pytest.mark.parametrize('kind',['missing_config','unknown_config','bad_platform','shop_unfiltered','timezone','field_code',
    'duplicate_target','default_override','nested_default','unknown_required','attribute_template','format_template','unknown_template','missing_pk_template'])
def test_uninterpretable_mapping_fails_closed(kind):
    value=mapping();config=value['snapshot_materialization']
    if kind=='missing_config':value.pop('snapshot_materialization')
    elif kind=='unknown_config':config['execute']='private-sentinel'
    elif kind=='bad_platform':config['platform']='../wrong'
    elif kind=='shop_unfiltered':config['shop_key']='site_name'
    elif kind=='timezone':config['source_timezone']='local'
    elif kind=='field_code':value['field_mappings'][0]['expression']='row.secret'
    elif kind=='duplicate_target':value['field_mappings'][1]['target']='siteId'
    elif kind=='default_override':config['property_defaults']['name']='fake'
    elif kind=='nested_default':config['property_defaults']['nested']={'secret':'value'}
    elif kind=='unknown_required':value['validation']['required']=['missing']
    elif kind=='attribute_template':value['unique_key_pattern']='{pk.__class__}'
    elif kind=='format_template':value['unique_key_pattern']='{pk!r}'
    elif kind=='unknown_template':value['unique_key_pattern']='{unknown}:{pk}'
    else:value['unique_key_pattern']='constant'
    with pytest.raises(ValueError):compiled(value)


@pytest.mark.parametrize('kind',['extra','missing','blank_name','int_bool','int_string','string_number','negative_time','float_time','filter','duplicate','too_many','naive'])
def test_bad_rows_cannot_be_partially_materialized(kind):
    raw=row();rows=[raw];at=NOW
    if kind=='extra':raw['site_tel']='private-sentinel'
    elif kind=='missing':raw.pop('logo')
    elif kind=='blank_name':raw['site_name']=' '
    elif kind=='int_bool':raw['site_id']=True
    elif kind=='int_string':raw['site_id']='1'
    elif kind=='string_number':raw['site_name']=42
    elif kind=='negative_time':raw['create_time']=-1
    elif kind=='float_time':raw['create_time']=1.5
    elif kind=='filter':raw['site_id']=2
    elif kind=='duplicate':rows=[raw,deepcopy(raw)]
    elif kind=='too_many':rows=[raw]*1001
    else:at=NOW.replace(tzinfo=None)
    with pytest.raises(ValueError) as error:materialize_snapshot(rows,compiled(),observed_at=at)
    assert 'private-sentinel' not in str(error.value)


def test_compilation_detaches_caller_documents():
    value=mapping();plan=compiled(value)
    value['snapshot_materialization']['property_defaults']['currency']='USD'
    value['field_mappings'][0]['target']='changed'
    result=materialize_snapshot([row()],plan,observed_at=NOW)[0]
    assert result['properties']['currency']=='CNY' and result['properties']['siteId']==1


def test_duplicate_source_key_cannot_hide_in_different_external_ids():
    value=mapping();value['unique_key_pattern']='niushop:{site_name}:{pk}'
    first=row();second=row();second['site_name']='另一个名字'
    with pytest.raises(ValueError):materialize_snapshot([first,second],compiled(value),observed_at=NOW)


def test_declared_filter_must_match_bound_read_scope():
    value=mapping();value['site_filter']='site_id=2'
    with pytest.raises(ValueError):compiled(value)


def test_declared_output_enters_existing_canonical_object_kernel():
    from aos_api.ecom_core_models import SyncScope
    from aos_api.ec_ot_writer import _normalize_rows
    plan=compiled()
    output=materialize_snapshot([row()],plan,observed_at=NOW)
    scope=SyncScope(org_id='org-org',workspace_id='dev-project',platform=plan.platform,shop_or_marketplace_id=plan.shop_id,stream='P01-shop-qyh')
    objects,links=_normalize_rows(output,scope)
    assert not links and len(objects)==1
    assert objects[0].identity.external_id=='niushop:1:1'
    assert objects[0].properties['siteId']==1
    assert len(objects[0].properties)==14
