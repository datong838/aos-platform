"""Diagnostic counts only; no source access or relationship writes."""
import importlib.util
from pathlib import Path
import pytest
spec=importlib.util.spec_from_file_location('relation_audit',Path(__file__).resolve().parents[3]/'scripts/audit_niushop_snapshot_relationships.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def row(ot,key,**props):return dict(ot=ot,source_pk=str(key),is_deleted=False,properties=props)
def inputs():
    result={name:[] for name in module.TYPES}
    result.update(Order=[row('Order',1,createdAt='2026-09-01T00:00:00+08:00',orderNo='fixture',memberId=1)],
        OrderLine=[row('OrderLine',2,orderId=1,orderNo='fixture',memberId=1,productId=3,skuId=0,createTime=None)],
        Product=[row('Product',3,shopId=1,categoryId='4,5')],Category=[row('Category',4),row('Category',5)],
        Shop=[row('Shop',1)],CustomerLite=[row('CustomerLite',1)],Payment=[row('Payment',6,orderId='1',memberId=1)])
    return result

def test_current_mapping_aliases_and_parent_order_window():
    report=module.audit(inputs())
    assert report['relations']['OrderLine.ofProduct']['matched']==1
    assert report['relations']['Product.inCategory']['matched']==2
    assert report['relations']['OrderLine.ofSku']['unset']==1
    assert report['relations']['Order.hasPayment']['matched']==1
    assert report['orderLineWindow']['parentTimeAvailable']==1
    assert report['orderLineWindow']['ownTimeUnknown']==1
    assert report['crossChecks']['OrderLine.orderNo']['matched']==1
    assert report['relations']['Order.fromWeapp']['status']=='unsupported-mapping'
    assert report['relationshipsWritten'] is False

@pytest.mark.parametrize('key',[True,0,-1,'01',' 1','+1','1.0','١','9223372036854775808'])
def test_invalid_relation_key_is_not_a_match(key):
    data=inputs();data['Payment'][0]['properties']['orderId']=key
    report=module.audit(data)['relations']['Order.hasPayment']
    assert report['matched']==0
    assert report['unset' if type(key) is int and key==0 else 'invalid']==1

def test_missing_parent_and_tombstone_are_explicit():
    data=inputs();data['Order'][0]['is_deleted']=True
    data['Product']=[]
    report=module.audit(data)
    assert report['relations']['Order.lines']['deletedEndpoint']==1
    assert report['relations']['OrderLine.ofProduct']['missingParent']==1
    assert report['orderLineWindow']['parentDeleted']==1

@pytest.mark.parametrize('fault',['duplicate','missing_type','wrong_type','link'])
def test_invalid_cohort_is_rejected(fault):
    data=inputs()
    if fault=='duplicate':data['Order']*=2
    elif fault=='missing_type':data.pop('Shop')
    elif fault=='wrong_type':data['Order'][0]['ot']='Product'
    else:data['Order'][0]['link_type']='Order.lines'
    with pytest.raises(ValueError):module.audit(data)
