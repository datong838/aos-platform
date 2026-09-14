from copy import deepcopy
from dataclasses import replace
import pytest
from test_pipeline_snapshot_business_cohort import fixture, row, START, END
from aos_api.pipeline_snapshot_business_cohort import compile_business_cohort_policy
from aos_api.pipeline_snapshot_relationship_quality import compile_relationship_quality_policy
from aos_api.pipeline_snapshot_fact_quality import compile_fact_quality_policy, measure_fact_quality


def setup():
    relation, document = fixture()
    cohort = compile_business_cohort_policy(document, relationship_policy=relation)
    quality = compile_relationship_quality_policy(dict(schemaVersion='aos.snapshot-relationship-quality/v1',
        relationshipPolicyHash=relation.content_hash,purposes=[dict(purposeCode='store_analysis',rules=[
            dict(linkType='Order.lines',requirement='required')])]),relationship_policy=relation)
    fields = dict(schemaVersion='aos.snapshot-fact-quality/v1',cohortPolicyHash=cohort.content_hash,
        relationshipQualityPolicyHash=quality.content_hash,purposeCode='store_analysis',facts=[
            dict(objectType=ot,fields=[dict(property='name',kind='nonblank-string')]) for ot in relation.object_types])
    return relation,cohort,quality,fields


def measure(outputs, edit=None):
    relation,cohort,quality,document=setup()
    if edit:edit(document)
    policy=compile_fact_quality_policy(document,relationship_policy=relation,cohort_policy=cohort,quality_policy=quality)
    return measure_fact_quality(outputs,relation,cohort,quality,policy,window_start=START,window_end=END,observed_at=END)


def rows():
    return dict(Order=[row('Order',1,createdAt=START.isoformat(),name='order')],
        OrderLine=[row('OrderLine',1,orderId=1,name='line')],Product=[row('Product',1,status='ACTIVE',name='product')])


def test_joint_counts_preserve_unknown_and_historical_exclusions():
    value=rows()
    value['Order'] += [row('Order',2,name='unknown-time'),row('Order',3,createdAt='2020-01-01T00:00:00+00:00')]
    value['OrderLine'] += [row('OrderLine',2,orderId=99,name='missing-parent'),row('OrderLine',3,orderId=3)]
    value['Product'] += [row('Product',2,status='ACTIVE',name=''),row('Product',3,status='INACTIVE')]
    original=deepcopy(value); result=measure(value)
    for ot in ('Order','OrderLine','Product'):
        assert result['facts'][ot]['counts']==dict(observedCount=3,eligibleCount=2,validCount=1,excludedCount=1,duplicateCount=0)
    assert result['facts']['OrderLine']['relationshipIssues']=={'Order.lines':1}
    assert value==original


@pytest.mark.parametrize('kind,good,bad',[
    ('nonblank-string','abc','  '),('positive-id','123','001'),
    ('nonnegative-integer',0,True),('nonnegative-number',1.5,True),
    ('positive-integer',1,0),('positive-integer',2,'2'),
    ('nonnegative-number',0,float('nan')),('nonnegative-number',1,float('inf')),
    ('boolean',False,0),('timestamp',START.isoformat(),'1970-01-01T00:00:00+00:00'),
    ('timestamp',START.isoformat(),'2026-01-01T00:00:00'),('enum','PAID','UNKNOWN'),
    ('enum',1,True),
])
def test_field_predicates_are_strict(kind,good,bad):
    def edit(doc):
        field=dict(property='field',kind=kind)
        if kind=='enum':field['values']=[good]
        next(f for f in doc['facts'] if f['objectType']=='Product')['fields'].append(field)
    for value,valid in ((good,1),(bad,0)):
        output=rows();output['Product'][0]['properties']['field']=value
        assert measure(output,edit)['facts']['Product']['counts']['validCount']==valid


def test_empty_facts_stay_zero():
    result=measure(dict(Order=[],OrderLine=[],Product=[]))
    assert all(item['counts']['eligibleCount']==0 and item['counts']['validCount']==0 for item in result['facts'].values())


@pytest.mark.parametrize('fault',['hash','missing','duplicate','empty-fields','kind','enum-bool'])
def test_policy_requires_complete_nonempty_field_semantics(fault):
    relation,cohort,quality,doc=setup()
    if fault=='hash':doc['cohortPolicyHash']='sha256:'+'0'*64
    if fault=='missing':doc['facts'].pop()
    if fault=='duplicate':doc['facts'][1]=deepcopy(doc['facts'][0])
    if fault=='empty-fields':doc['facts'][0]['fields']=[]
    if fault=='kind':doc['facts'][0]['fields'][0]['kind']='python-expression'
    if fault=='enum-bool':doc['facts'][0]['fields']=[dict(property='name',kind='enum',values=[True])]
    with pytest.raises(ValueError):compile_fact_quality_policy(doc,relationship_policy=relation,cohort_policy=cohort,quality_policy=quality)


def test_compiled_policy_cannot_be_forged():
    relation,cohort,quality,doc=setup()
    policy=compile_fact_quality_policy(doc,relationship_policy=relation,cohort_policy=cohort,quality_policy=quality)
    with pytest.raises(ValueError):measure_fact_quality(rows(),relation,cohort,quality,
        replace(policy,content_hash='sha256:'+'0'*64),window_start=START,window_end=END,observed_at=END)


def test_separately_good_fields_cannot_be_averaged_into_a_valid_row():
    output=rows()
    output['Product']=[row('Product',1,status='ACTIVE',name='valid',price=-1),
        row('Product',2,status='ACTIVE',name='',price=100)]
    def edit(document):
        next(f for f in document['facts'] if f['objectType']=='Product')['fields'].append(
            dict(property='price',kind='nonnegative-number'))
    result=measure(output,edit)['facts']['Product']
    assert result['counts']['eligibleCount']==2 and result['counts']['validCount']==0
    assert result['fieldIssues']=={'name':1,'price':1}


@pytest.mark.parametrize('purpose,valid',[('store_analysis',1),('customer_analysis',0)])
def test_disclosed_relationship_is_visible_without_replacing_required_semantics(purpose,valid):
    from test_pipeline_snapshot_relationship_quality import fixture as relationship_fixture
    relation,usage,_=relationship_fixture()
    quality=compile_relationship_quality_policy(usage,relationship_policy=relation)
    cohort=compile_business_cohort_policy(dict(schemaVersion='aos.snapshot-business-cohort/v1',
        relationshipPolicyHash=relation.content_hash,purposeCode=purpose,windowBoundary='start-inclusive-end-exclusive',
        rules=[dict(objectType=ot,basis='snapshot',statusFilter=None) for ot in relation.object_types]),relationship_policy=relation)
    document=dict(schemaVersion='aos.snapshot-fact-quality/v1',cohortPolicyHash=cohort.content_hash,
        relationshipQualityPolicyHash=quality.content_hash,purposeCode=purpose,
        facts=[dict(objectType=ot,fields=[dict(property='name',kind='nonblank-string')]) for ot in relation.object_types])
    policy=compile_fact_quality_policy(document,relationship_policy=relation,cohort_policy=cohort,quality_policy=quality)
    result=measure_fact_quality(dict(Order=[row('Order',1,name='order',customer=99,owner=1)],
        Customer=[row('Customer',1,name='customer')]),relation,cohort,quality,policy,window_start=START,window_end=END,observed_at=END)
    assert result['facts']['Order']['counts']['validCount']==valid
    assert result['facts']['Order']['relationshipIssues']=={'Order.customer':1,'Order.owner':0}
