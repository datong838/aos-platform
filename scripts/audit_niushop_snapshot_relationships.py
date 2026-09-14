"""Read-only diagnostic of one complete Niushop canonical cohort; never writes links."""
import re
from datetime import datetime

TYPES=('Shop','Product','ProductSku','Category','Order','OrderLine','Shipment','CustomerLite','Weapp','SystemConfig','ProductReview','Payment')
# Child properties name the parent. Link direction remains the canonical registry's.
RELATIONS=(
 ('ProductSku.ofProduct','ProductSku','productId','Product'),
 ('Product.inCategory','Product','categoryId','Category'),
 ('Shop.sellsProduct','Product','shopId','Shop'),
 ('Order.lines','OrderLine','orderId','Order'),
 ('OrderLine.ofProduct','OrderLine','productId','Product'),
 ('OrderLine.ofSku','OrderLine','skuId','ProductSku'),
 ('Order.fulfilledBy','Shipment','orderId','Order'),
 ('Order.placedByLite','Order','memberId','CustomerLite'),
 ('Shop.hasWeapp','Weapp','siteId','Shop'),
 ('Product.hasReview','ProductReview','productId','Product'),
 ('ProductReview.ofSku','ProductReview','skuId','ProductSku'),
 ('ProductReview.byMember','ProductReview','memberId','CustomerLite'),
 ('Order.hasPayment','Payment','orderId','Order'),
)


def _key(value):
    if type(value) is int and 0<value<=9223372036854775807:return str(value)
    if type(value) is str and re.fullmatch(r'[1-9][0-9]{0,18}',value) and int(value)<=9223372036854775807:return value
    raise ValueError('canonical positive relationship key required')


def _unset(value):return type(value) in (str,int) and value in (0,'0','')


def _timestamp(value):
    if type(value) is not str:return False
    try:return datetime.fromisoformat(value.replace('Z','+00:00')).utcoffset() is not None
    except ValueError:return False


def audit(outputs):
    if type(outputs) is not dict or set(outputs)!=set(TYPES):raise ValueError('complete twelve-type cohort required')
    indexed={}
    for ot,rows in outputs.items():
        if type(rows) is not list or len(rows)>=1000:raise ValueError('bounded complete object list required')
        index={}
        for row in rows:
            if (type(row) is not dict or row.get('ot')!=ot or 'link_type' in row
                    or type(row.get('properties')) is not dict or type(row.get('is_deleted')) is not bool):
                raise ValueError('canonical object only')
            key=_key(row['source_pk'])
            if key in index:raise ValueError('duplicate object identity')
            index[key]=row
        indexed[ot]=index
    report={'schemaVersion':'aos.developer-niushop-relationship-audit/v1','relationshipsWritten':False,
        'formalFulfillment':False,'relations':{},'crossChecks':{},
        'unsupportedChecks':['Order.fromWeapp: no exact mapped source key',
            'Payment.currentTradeNumber: parent Order out_trade_no not selected',
            'Shipment.tracking: deliberately redacted','ProductReview.text: deliberately not selected',
            'SystemConfig.values: deliberately not selected']}
    relations=RELATIONS
    if outputs['Order'] and all('weappId' in row['properties'] for row in outputs['Order']):
        relations=relations+(('Order.fromWeapp','Order','weappId','Weapp'),)
    for name,child,field,parent_type in relations:
        counts=dict(rows=len(outputs[child]),references=0,matched=0,missingParent=0,missingKey=0,invalid=0,unset=0,deletedEndpoint=0)
        for row in outputs[child]:
            value=row['properties'].get(field)
            if value is None:counts['missingKey']+=1;continue
            if _unset(value):counts['unset']+=1;continue
            if name=='Product.inCategory' and type(value) is str and value.startswith(',') and value.endswith(','):
                value=value[1:-1]
            values=value.split(',') if name=='Product.inCategory' and type(value) is str else [value]
            try:
                keys=[_key(item) for item in values]
                if len(set(keys))!=len(keys):raise ValueError('duplicate category key')
            except ValueError:counts['invalid']+=1;continue
            for key in keys:
                counts['references']+=1
                parent=indexed[parent_type].get(key)
                if parent is None:counts['missingParent']+=1
                else:
                    counts['matched']+=1
                    if row['is_deleted'] or parent['is_deleted']:counts['deletedEndpoint']+=1
        report['relations'][name]=counts
    if 'Order.fromWeapp' not in report['relations']:
        report['relations']['Order.fromWeapp']={'status':'unsupported-mapping','rows':len(outputs['Order'])}
    else:report['unsupportedChecks'].remove('Order.fromWeapp: no exact mapped source key')
    window=dict(rows=len(outputs['OrderLine']),parentTimeAvailable=0,parentMissing=0,parentTimeUnknown=0,parentDeleted=0,ownTimeUnknown=0)
    for row in outputs['OrderLine']:
        if not _timestamp(row['properties'].get('createTime')):window['ownTimeUnknown']+=1
        try:parent=indexed['Order'].get(_key(row['properties'].get('orderId')))
        except ValueError:parent=None
        if parent is None:window['parentMissing']+=1;continue
        if parent['is_deleted']:window['parentDeleted']+=1
        window['parentTimeAvailable' if _timestamp(parent['properties'].get('createdAt')) else 'parentTimeUnknown']+=1
    report['orderLineWindow']=window|{'basis':'parent-order-createdAt','sourceTimeRewritten':False}
    for child,field in [('OrderLine','orderNo'),('OrderLine','memberId'),('Payment','memberId'),('Shipment','memberId')]:
        counts=dict(matched=0,mismatch=0,unavailable=0)
        for row in outputs[child]:
            try:parent=indexed['Order'].get(_key(row['properties'].get('orderId')))
            except ValueError:parent=None
            left=row['properties'].get(field);right=parent['properties'].get(field) if parent else None
            if left is None or right is None:counts['unavailable']+=1
            else:counts['matched' if type(left) is type(right) and left==right else 'mismatch']+=1
        report['crossChecks'][child+'.'+field]=counts
    trades=dict(same=0,different=0,unavailable=0,relationInvalidated=False)
    for row in outputs['Payment']:
        try:parent=indexed['Order'].get(_key(row['properties'].get('orderId')))
        except ValueError:parent=None
        left=row['properties'].get('outTradeNo');right=parent['properties'].get('outTradeNo') if parent else None
        if type(left) is not str or not left or type(right) is not str or not right:trades['unavailable']+=1
        else:trades['same' if left==right else 'different']+=1
    report['paymentTradeComparison']=trades
    if outputs['Order'] and all('outTradeNo' in row['properties'] for row in outputs['Order']):
        report['unsupportedChecks'].remove('Payment.currentTradeNumber: parent Order out_trade_no not selected')
    return report
