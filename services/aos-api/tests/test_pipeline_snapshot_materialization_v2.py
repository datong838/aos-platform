from copy import deepcopy
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import pytest

from aos_api.pipeline_snapshot_materialization import compile_snapshot_mapping, materialize_snapshot
from aos_api.pipeline_source_selection import MappingReadSpec


NOW = datetime(2026, 9, 13, tzinfo=timezone.utc)


def declaration():
    kinds = [('goods_id','int'),('site_id','int'),('name','string'),('category_id','string'),('price','decimal'),
             ('content','text'),('modify_time','timestamp'),('create_time','timestamp'),
             ('is_delete','int'),('goods_state','int')]
    return dict(source_table='ns_goods', target_ot='Product', primary_key='goods_id',
        incremental_strategy='snapshot', site_filter='site_id=1', unique_key_pattern='niushop:{site_id}:{pk}',
        field_mappings=[dict(source=n,target={'site_id':'shopId','name':'title','category_id':'categoryId'}.get(n,n),type=k) for n,k in kinds], validation={'required':['goods_id','site_id','name']},
        snapshot_materialization=dict(schema_version='aos.snapshot-materialization/v2',platform='niushop',
            shop_key='site_id',source_timezone='+08:00',property_defaults={},
            source_updated_at={'primary':'modify_time','fallback':'create_time'},
            tombstone={'field':'is_delete','live_value':0,'deleted_value':1},
            status={'field':'goods_state','property_target':'status','values':{'0':'INACTIVE','1':'ACTIVE'}}))


def compiled(value=None):
    value = value or declaration()
    spec = MappingReadSpec('ns_goods','Product','goods_id',tuple(f['source'] for f in value['field_mappings']),(('site_id',1),))
    return compile_snapshot_mapping(value,spec)


def row():
    return dict(goods_id=1,site_id=1,name='测试商品',category_id='1',price=Decimal('1234567890.123456789012345678'),
        content='<p>原文</p>',modify_time=int(NOW.timestamp())-10,create_time=int(NOW.timestamp())-20,is_delete=0,goods_state=1)


def test_decimal_source_time_and_repeated_observation_preserve_real_facts():
    plan=compiled(); source=row(); original=deepcopy(source)
    result=materialize_snapshot([source],plan,observed_at=NOW)
    assert result == materialize_snapshot([source],plan,observed_at=NOW+timedelta(hours=1))
    assert source==original
    assert result[0]['properties']['price']=='1234567890.123456789012345678'
    assert result[0]['properties']['content']=='<p>原文</p>'
    assert result[0]['source_updated_at']==NOW-timedelta(seconds=10)
    assert result[0]['status_raw']=='ACTIVE'


def test_explicit_tombstone_and_off_shelf_status_enter_canonical_kernel():
    from aos_api.ec_ot_writer import _normalize_rows
    from aos_api.ecom_core_models import SyncScope
    rows=[row()|{'goods_state':0},row()|{'goods_id':2,'is_delete':1,'modify_time':0}]
    result=materialize_snapshot(rows,compiled(),observed_at=NOW)
    assert result[0]['status_raw']=='INACTIVE' and not result[0]['is_deleted']
    assert result[1]['status_raw']=='DELETED' and result[1]['is_deleted']
    assert result[1]['source_updated_at']==NOW-timedelta(seconds=20)
    objects,links=_normalize_rows(result,SyncScope(org_id='org-org',workspace_id='dev-project',platform='niushop',shop_or_marketplace_id='1',stream='P02-product-qyh'))
    assert len(objects)==2 and not links and objects[1].is_deleted
    assert objects[0].properties['price']==str(row()['price'])


@pytest.mark.parametrize('value',[1.5,True,'1.50',Decimal('NaN'),Decimal('Infinity'),Decimal('1e100'),Decimal('1e-19')])
def test_unsafe_decimal_rejects_entire_batch(value):
    with pytest.raises(ValueError,match='SNAPSHOT_MATERIALIZATION_INVALID'):
        materialize_snapshot([row(),row()|{'goods_id':2,'price':value}],compiled(),observed_at=NOW)


@pytest.mark.parametrize('changes',[{'modify_time':0,'create_time':0},{'modify_time':int(NOW.timestamp())+1},
    {'is_delete':2},{'goods_state':9},{'content':'x'*262145},{'site_id':2},{'extra':'private'}])
def test_invalid_source_facts_fail_closed(changes):
    with pytest.raises(ValueError,match='SNAPSHOT_MATERIALIZATION_INVALID'):
        materialize_snapshot([row()|changes],compiled(),observed_at=NOW)


@pytest.mark.parametrize('change',['links','missing_clock','unknown_clock','unselected_delete','unknown_status','duplicate_delete','unknown_config'])
def test_unknown_or_incomplete_declaration_is_not_silently_ignored(change):
    value=declaration();config=value['snapshot_materialization']
    if change=='links':value['links']=[{'name':'hasSku'}]
    elif change=='missing_clock':config.pop('source_updated_at')
    elif change=='unknown_clock':config['source_updated_at']['primary']='price'
    elif change=='unselected_delete':config['tombstone']['field']='missing'
    elif change=='unknown_status':config['status']['values']['1']='arbitrary lower case'
    elif change=='duplicate_delete':config['tombstone']['deleted_value']=0
    else:config['execute']='private'
    with pytest.raises(ValueError,match='SNAPSHOT_MAPPING_INVALID'):compiled(value)


def test_compiled_plan_is_detached_from_later_declaration_changes():
    value=declaration();plan=compiled(value)
    value['snapshot_materialization']['status']['values']['1']='DELETED'
    assert materialize_snapshot([row()],plan,observed_at=NOW)[0]['status_raw']=='ACTIVE'


@pytest.mark.parametrize('change',['default_status','overwrite_target','delete_as_live_status'])
def test_state_cannot_be_fabricated_or_overwrite_declared_properties(change):
    value=declaration(); config=value['snapshot_materialization']
    if change=='default_status':config['property_defaults']['status']='active'
    elif change=='overwrite_target':config['status']['property_target']='title'
    else:config['status']['values']['1']='DELETED'
    with pytest.raises(ValueError,match='SNAPSHOT_MAPPING_INVALID'):compiled(value)


def test_repeated_poll_does_not_emit_a_second_authoritative_product_change():
    from sqlalchemy import create_engine, select
    from aos_api.ecom_consistency_store import EcomConsistencyStore,metadata,projection_outbox
    from aos_api.ec_ot_writer import _normalize_rows
    from aos_api.ecom_core_models import SyncScope
    from test_ecom_consistency_store import batch
    engine=create_engine('sqlite+pysqlite:///:memory:')
    metadata.create_all(engine); store=EcomConsistencyStore(engine)
    scope=SyncScope(org_id='org-org',workspace_id='dev-project',platform='niushop',shop_or_marketplace_id='1',stream='P02-product-qyh')
    try:
        for index in range(2):
            output=materialize_snapshot([row()],compiled(),observed_at=NOW+timedelta(hours=index))
            objects,_=_normalize_rows(output,scope)
            store.apply_batch(batch(*objects,key=f'poll-{index}',expected=index,batch_scope=scope))
        with engine.connect() as conn:
            assert len(conn.execute(select(projection_outbox)).all())==1
    finally:engine.dispose()
