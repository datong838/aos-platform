from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone, timedelta
import pytest
from aos_api.pipeline_snapshot_relationships import compile_relationship_policy
from aos_api.pipeline_snapshot_business_cohort import compile_business_cohort_policy, select_business_cohort

END=datetime(2026,9,14,tzinfo=timezone.utc)
START=END-timedelta(days=30)


def fixture():
    relation=compile_relationship_policy(dict(schemaVersion='aos.snapshot-relationships/v1',
        objectTypes=['Order','OrderLine','Product'],rules=[dict(linkType='Order.lines',rowType='OrderLine',
            parentType='Order',referenceProperty='orderId',direction='parent-to-row',encoding='positive-id',allowUnset=False)]))
    document=dict(schemaVersion='aos.snapshot-business-cohort/v1',relationshipPolicyHash=relation.content_hash,
        purposeCode='store_analysis',windowBoundary='start-inclusive-end-exclusive',rules=[
            dict(objectType='Order',basis='own-time',timeProperty='createdAt',statusFilter=None),
            dict(objectType='OrderLine',basis='parent-time',parentType='Order',referenceProperty='orderId',timeProperty='createdAt',statusFilter=None),
            dict(objectType='Product',basis='snapshot',statusFilter=dict(property='status',known=['ACTIVE','INACTIVE'],accepted=['ACTIVE']))])
    return relation,document


def row(ot,key,deleted=False,**props):
    return dict(ot=ot,source_pk=str(key),is_deleted=deleted,properties=props)


def select(outputs, document=None):
    relation,default=fixture()
    policy=compile_business_cohort_policy(default if document is None else document,relationship_policy=relation)
    return select_business_cohort(outputs,relation,policy,window_start=START,window_end=END,observed_at=END)


def test_recent_orders_and_products_partition_without_changing_raw_history():
    outputs=dict(Order=[row('Order',i,createdAt=(END-timedelta(days=1 if i<=5 else 60)).isoformat()) for i in range(1,126)]
        +[row('Order',i,True,createdAt=START.isoformat()) for i in range(126,186)],OrderLine=[],
        Product=[row('Product',i,i>57,status='ACTIVE' if i<=39 else 'INACTIVE') for i in range(1,66)])
    before=deepcopy(outputs);result=select(outputs)
    orders,products=result.cohorts['Order'],result.cohorts['Product']
    assert (orders.observed_count,orders.eligible_count,len(orders.included_keys),len(orders.excluded))==(185,5,5,180)
    assert (products.observed_count,products.eligible_count,len(products.excluded))==(65,39,26)
    assert [reason for _,reason in products.excluded].count('status-outside')==18
    assert [reason for _,reason in products.excluded].count('deleted')==8
    assert outputs==before


def test_line_uses_parent_time_but_missing_parent_stays_in_denominator():
    outputs=dict(Order=[row('Order',1,createdAt=(END-timedelta(days=2)).isoformat()),
        row('Order',2,createdAt=(START-timedelta(days=1)).isoformat()),row('Order',3,True)],
        OrderLine=[row('OrderLine',i,orderId=parent,createTime=None) for i,parent in enumerate([1,2,3,99,'01'],1)],Product=[])
    result=select(outputs).cohorts['OrderLine']
    assert result.included_keys==('1',)
    assert result.eligible_count==3 and len(result.unknown)==2 and len(result.excluded)==2
    assert dict(result.unknown)=={'4':('missing-parent',),'5':('invalid-parent-reference',)}


@pytest.mark.parametrize('timestamp', [None, True, 'invalid', '2026-09-01T00:00:00',
    '1970-01-01T00:00:00+00:00', (END+timedelta(seconds=1)).isoformat()])
def test_unknown_or_future_time_cannot_disappear_from_denominator(timestamp):
    result=select(dict(Order=[row('Order',1,createdAt=timestamp)],OrderLine=[],Product=[])).cohorts['Order']
    assert result.eligible_count==1 and len(result.unknown)==1 and not result.included_keys and not result.excluded


def test_window_boundaries_and_unknown_product_status():
    outputs=dict(Order=[row('Order',1,createdAt=START.isoformat()),row('Order',2,createdAt=END.isoformat())],
        OrderLine=[],Product=[row('Product',1,status='UNKNOWN'),row('Product',2)])
    result=select(outputs)
    assert result.cohorts['Order'].included_keys==('1',)
    assert result.cohorts['Order'].excluded==(('2','time-outside'),)
    assert result.cohorts['Product'].eligible_count==2 and len(result.cohorts['Product'].unknown)==2


@pytest.mark.parametrize('fault',['hash','missing','duplicate','parent','undeclared_reference','status','boundary','extra'])
def test_policy_requires_complete_explicit_semantics(fault):
    relation,document=fixture()
    if fault=='hash':document['relationshipPolicyHash']='sha256:'+'0'*64
    if fault=='missing':document['rules'].pop()
    if fault=='duplicate':document['rules'][2]=deepcopy(document['rules'][0])
    if fault=='parent':document['rules'][1]['parentType']='Unknown'
    if fault=='undeclared_reference':document['rules'][1]['referenceProperty']='anotherId'
    if fault=='status':document['rules'][2]['statusFilter']['accepted']=['OTHER']
    if fault=='boundary':document['windowBoundary']='inclusive'
    if fault=='extra':document['ready']=True
    with pytest.raises(ValueError):compile_business_cohort_policy(document,relationship_policy=relation)


def test_compiled_policy_and_time_scope_are_revalidated():
    relation,document=fixture();policy=compile_business_cohort_policy(document,relationship_policy=relation)
    empty=dict(Order=[],OrderLine=[],Product=[])
    with pytest.raises(ValueError):select_business_cohort(empty,relation,replace(policy,content_hash='sha256:'+'0'*64),window_start=START,window_end=END,observed_at=END)
    with pytest.raises(ValueError):select_business_cohort(empty,relation,policy,window_start=END,window_end=START,observed_at=END)
    with pytest.raises(ValueError):select_business_cohort(empty,relation,policy,window_start=START,window_end=END,observed_at=START)
    assert select(empty).cohorts['Order'].observed_count==0
