from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest
import yaml
from aos_api.pipeline_source_selection import MappingReadSpec
from aos_api.pipeline_snapshot_materialization import compile_snapshot_mapping,materialize_snapshot

NOW=datetime(2026,9,14,tzinfo=timezone.utc)


def mapping():
    root=Path(__file__).resolve().parents[3]
    value=yaml.safe_load((root/'bundles/candidates/ecommerce/platform.ecommerce.niushop/1.6.0/content/mappings/p04-category.yaml').read_text())
    for name in ('links','incremental_cursor'):value.pop(name)
    value['validation']={'required':['category_id','site_id','category_name']}
    for field in value['field_mappings']:
        if field['source']=='pid':field['target']='parentCategoryId'
    value['snapshot_materialization']=dict(schema_version='aos.snapshot-materialization/v3',platform='niushop',
        shop_key='site_id',source_timezone='+08:00',property_defaults={},time_basis='observation',
        deletion_basis='row-presence-only',status=dict(field='is_show',property_target='status',values={'0':'INACTIVE','1':'ACTIVE'}))
    return value


def compiled(value=None):
    value=value or mapping()
    spec=MappingReadSpec('ns_goods_category','Category','category_id',
        tuple(f['source'] for f in value['field_mappings']),(('site_id',1),))
    return compile_snapshot_mapping(value,spec)


def row():
    return {f['source']:(1 if f['type']=='int' else 'synthetic') for f in mapping()['field_mappings']}


def test_observation_clock_is_explicit_and_canonical_without_source_time():
    from aos_api.ec_ot_writer import _normalize_rows
    from aos_api.ecom_core_models import SyncScope
    plan=compiled();raw=row();before=deepcopy(raw)
    output=materialize_snapshot([raw],plan,observed_at=NOW)
    obj=output[0]
    assert obj['source_updated_at']==NOW and raw==before
    assert obj['properties']['sourceUpdatedAtBasis']=='observation'
    assert obj['properties']['sourceModificationTimeKnown'] is False
    assert 'sourceModifiedAt' not in obj['properties']
    objects,links=_normalize_rows(output,SyncScope(org_id='org-org',workspace_id='dev-project',
        platform='niushop',shop_or_marketplace_id='1',stream='P04-category-qyh'))
    assert len(objects)==1 and links==[]
    assert objects[0].properties['updatedAt']=='2026-09-14T00:00:00.000000Z'
    assert objects[0].properties['observedAt']=='2026-09-14T00:00:00.000000Z'
    later=materialize_snapshot([raw],plan,observed_at=NOW+timedelta(hours=1))[0]
    assert later['properties']['sourceModificationTimeKnown'] is False
    assert materialize_snapshot([],plan,observed_at=NOW)==[] # Absence never creates a tombstone.
    hidden=materialize_snapshot([raw|{'is_show':0}],plan,observed_at=NOW)[0]
    assert hidden['status_raw']=='INACTIVE' and hidden['is_deleted'] is False


@pytest.mark.parametrize('fault',['time','deletion','reserved','reserved_timezone','constant_state','links','unknown_key'])
def test_invalid_observation_declarations_rejected(fault):
    value=mapping();cfg=value['snapshot_materialization']
    if fault=='time':cfg['time_basis']='source'
    elif fault=='deletion':cfg['deletion_basis']='absence-is-delete'
    elif fault=='reserved':cfg['property_defaults']['sourceModificationTimeKnown']=True
    elif fault=='reserved_timezone':cfg['property_defaults']['observedAtSourceTimezone']='+1400'
    elif fault=='constant_state':cfg['property_defaults']['status']='ACTIVE'
    elif fault=='links':value['links']=[{'execute':'unsafe'}]
    else:cfg['private_callback']='unsafe'
    with pytest.raises(ValueError,match='SNAPSHOT_MAPPING_INVALID'):compiled(value)


@pytest.mark.parametrize('fault',['shop','extra','state','duplicate','naive_time'])
def test_invalid_observations_rejected(fault):
    raw=row();rows=[raw];at=NOW
    if fault=='shop':raw['site_id']=2
    elif fault=='extra':raw['private_column']='synthetic'
    elif fault=='state':raw['is_show']=9
    elif fault=='duplicate':rows.append(dict(raw))
    else:at=NOW.replace(tzinfo=None)
    with pytest.raises(ValueError,match='SNAPSHOT_MATERIALIZATION_INVALID'):
        materialize_snapshot(rows,compiled(),observed_at=at)


def test_observation_metadata_keeps_original_microsecond_precision():
    at=NOW.replace(microsecond=123456)
    obj=materialize_snapshot([row()],compiled(),observed_at=at)[0]
    assert datetime.fromisoformat(obj['properties']['observedAt'])==obj['source_updated_at']==at


def test_observation_snapshot_keeps_exact_decimal_and_rejects_lossy_float():
    from decimal import Decimal
    value=mapping()
    value['field_mappings'].append({'source':'synthetic_quantity','target':'syntheticQuantity','type':'decimal'})
    value['validation']['non_negative']=['synthetic_quantity']
    plan=compiled(value)
    raw=row()|{'synthetic_quantity':Decimal('1.230')}
    assert materialize_snapshot([raw],plan,observed_at=NOW)[0]['properties']['syntheticQuantity']=='1.230'
    for invalid in (1.23,Decimal('-1'),Decimal('NaN')):
        with pytest.raises(ValueError,match='SNAPSHOT_MATERIALIZATION_INVALID'):
            materialize_snapshot([raw|{'synthetic_quantity':invalid}],plan,observed_at=NOW)


def hierarchy_mapping():
    value=mapping()
    value['validation']['hierarchy']={'parent_field':'pid','root_value':0}
    return value


def test_category_hierarchy_accepts_shuffled_forest_and_deep_chain():
    plan=compiled(hierarchy_mapping())
    rows=[row()|{'category_id':3,'pid':2},row()|{'category_id':1,'pid':0},
          row()|{'category_id':4,'pid':0},row()|{'category_id':2,'pid':1}]
    assert len(materialize_snapshot(rows,plan,observed_at=NOW))==4
    deep=[row()|{'category_id':i,'pid':i-1} for i in range(1000,0,-1)]
    assert len(materialize_snapshot(deep,plan,observed_at=NOW))==1000


@pytest.mark.parametrize('parents',[{1:9},{1:1},{1:2,2:1},{0:0},{1:0,2:3,3:2}])
def test_category_hierarchy_rejects_orphans_cycles_and_root_collision(parents):
    rows=[row()|{'category_id':key,'pid':parent} for key,parent in parents.items()]
    with pytest.raises(ValueError,match='SNAPSHOT_MATERIALIZATION_INVALID'):
        materialize_snapshot(rows,compiled(hierarchy_mapping()),observed_at=NOW)


@pytest.mark.parametrize('fault',['missing_parent','text_parent','bool_root','extra_rule'])
def test_category_hierarchy_declaration_is_exact(fault):
    value=hierarchy_mapping();rule=value['validation']['hierarchy']
    if fault=='missing_parent':rule['parent_field']='not_selected'
    elif fault=='text_parent':rule['parent_field']='category_name'
    elif fault=='bool_root':rule['root_value']=False
    else:rule['custom']='unsafe'
    with pytest.raises(ValueError,match='SNAPSHOT_MAPPING_INVALID'):compiled(value)


def deletion_mapping():
    value=mapping()
    value['field_mappings'].append({'source':'is_delete','target':'isDelete','type':'int'})
    value['snapshot_materialization']['deletion_basis']={'field':'is_delete','live_value':0,'deleted_value':1}
    return value


def test_observation_snapshot_uses_only_explicit_source_deletion():
    plan=compiled(deletion_mapping())
    live=materialize_snapshot([row()|{'is_delete':0}],plan,observed_at=NOW)[0]
    deleted=materialize_snapshot([row()|{'is_delete':1}],plan,observed_at=NOW)[0]
    assert live['is_deleted'] is False and live['status_raw']=='ACTIVE'
    assert deleted['is_deleted'] is True and deleted['status_raw']=='DELETED'
    assert deleted['properties']['status']=='DELETED'
    assert deleted['properties']['sourceModificationTimeKnown'] is False
    assert materialize_snapshot([],plan,observed_at=NOW)==[]
    with pytest.raises(ValueError,match='SNAPSHOT_MATERIALIZATION_INVALID'):
        materialize_snapshot([row()|{'is_delete':2}],plan,observed_at=NOW)


@pytest.mark.parametrize('fault',['missing','text','equal','boolean','extra'])
def test_explicit_deletion_declaration_is_bound_to_selected_integer(fault):
    value=deletion_mapping();rule=value['snapshot_materialization']['deletion_basis']
    if fault=='missing':rule['field']='unselected'
    elif fault=='text':rule['field']='category_name'
    elif fault=='equal':rule['deleted_value']=0
    elif fault=='boolean':rule['live_value']=False
    else:rule['execute']='unsafe'
    with pytest.raises(ValueError,match='SNAPSHOT_MAPPING_INVALID'):compiled(value)


def test_public_projection_preserves_provenance_identity_and_schema_version():
    value=mapping()
    value['snapshot_materialization']['public_projection']={'schema_version':2,'properties':['status','parentCategoryId']}
    obj=materialize_snapshot([row()],compiled(value),observed_at=NOW)[0]
    assert obj['schema_version']==2 and obj['source_pk']=='1'
    assert set(obj['properties'])=={'status','parentCategoryId','updatedAt','observedAt','sourceUpdatedAtBasis','sourceModificationTimeKnown'}
    assert obj['properties']['sourceModificationTimeKnown'] is False
    assert 'id' not in obj['properties']


@pytest.mark.parametrize('projection',[
    {'schema_version':True,'properties':['status']},
    {'schema_version':0,'properties':['status']},
    {'schema_version':101,'properties':['status']},
    {'schema_version':2,'properties':['status','privateField']},
    {'schema_version':2,'properties':['status','status']},
    {'schema_version':2,'properties':['parentCategoryId']},
    {'schema_version':2,'properties':['status'],'extra':True},
])
def test_invalid_public_projection_rejected(projection):
    value=mapping();value['snapshot_materialization']['public_projection']=projection
    with pytest.raises(ValueError,match='SNAPSHOT_MAPPING_INVALID'):compiled(value)
