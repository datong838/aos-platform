"""Bounded public content, not source authentication or commercial outcome proof."""
from copy import deepcopy
from dataclasses import replace
import pytest
from tests.test_pipeline_snapshot_fact_quality import setup,rows
from tests.test_pipeline_snapshot_business_cohort import START,END,row
from aos_api.pipeline_snapshot_fact_quality import compile_fact_quality_policy
from aos_api.pipeline_snapshot_business_facts import compile_business_fact_policy,build_business_facts


def policies(group=False):
    relation,cohort,quality,document=setup()
    if group:next(x for x in document['facts'] if x['objectType']=='Product')['fields'].append(dict(property='status',kind='enum',values=['ACTIVE','INACTIVE']))
    fields=compile_fact_quality_policy(document,relationship_policy=relation,cohort_policy=cohort,quality_policy=quality)
    doc=dict(schemaVersion='aos.snapshot-business-facts/v1',fieldPolicyHash=fields.content_hash,purposeCode=fields.purpose_code,
        facts=[dict(objectType=ot,mode='group-counts' if group and ot=='Product' else 'records',
            fields=['status'] if group and ot=='Product' else ['name']) for ot in relation.object_types])
    return relation,cohort,quality,fields,doc


def build(output,group=False):
    relation,cohort,quality,fields,doc=policies(group)
    policy=compile_business_fact_policy(doc,field_policy=fields)
    return build_business_facts(output,relation,cohort,quality,fields,policy,window_start=START,window_end=END,observed_at=END)


def test_business_values_survive_without_unselected_or_raw_identity_fields():
    output=rows();output['Product'][0]['properties']['secret']='never-export'
    before=deepcopy(output);result=build(output)
    records=result['facts']['Product']['records']
    assert records[0]['values']=={'name':'product'} and records[0]['membership']=='known'
    assert records[0]['sourceKeyHash'].startswith('sha256:')
    assert 'never-export' not in str(result) and 'source_pk' not in str(result)
    assert output==before


def test_unknown_window_and_invalid_field_are_explicit_not_silently_dropped():
    output=rows();output['Order'].append(row('Order',2,name=''))
    result=build(output)['facts']['Order']
    assert len(result['records'])==2 and result['counts']['unknownRows']==1
    unknown=next(r for r in result['records'] if r['membership']=='unknown')
    assert unknown['values']=={'name':None} and unknown['invalidFields']==['name']


def test_historical_and_deleted_rows_are_excluded_without_exporting_values():
    output=rows();output['Order'].append(row('Order',2,createdAt='2020-01-01T00:00:00+00:00',name='historical-secret'))
    deleted=row('Product',2,status='ACTIVE',name='deleted-secret');deleted['is_deleted']=True;output['Product'].append(deleted)
    result=build(output)
    assert result['facts']['Order']['counts']['excludedCount']==1
    assert 'historical-secret' not in str(result) and 'deleted-secret' not in str(result)


def test_group_counts_are_explicit_status_not_sales():
    output=rows();result=build(output,True)['facts']['Product']
    assert result['groups']['status']['known']==[dict(value='ACTIVE',count=1)]
    assert result['groups']['status']['unknown']==[]
    assert result['groups']['status']['invalidKnown']==0


@pytest.mark.parametrize('fault',['hash','missing','extra','unknown-field','duplicate','free-text-group','mode'])
def test_policy_fails_closed(fault):
    *_,fields,doc=policies()
    if fault=='hash':doc['fieldPolicyHash']='sha256:'+'0'*64
    if fault=='missing':doc['facts'].pop()
    if fault=='extra':doc['extra']=True
    if fault=='unknown-field':doc['facts'][0]['fields']=['secret']
    if fault=='duplicate':doc['facts'][0]['fields']=['name','name']
    if fault=='free-text-group':doc['facts'][0]['mode']='group-counts'
    if fault=='mode':doc['facts'][0]['mode']='python'
    with pytest.raises(ValueError):compile_business_fact_policy(doc,field_policy=fields)


def test_compiled_policy_and_empty_facts_are_not_authority():
    relation,cohort,quality,fields,doc=policies()
    policy=compile_business_fact_policy(doc,field_policy=fields)
    with pytest.raises(ValueError):build_business_facts(rows(),relation,cohort,quality,fields,
        replace(policy,content_hash='sha256:'+'0'*64),window_start=START,window_end=END,observed_at=END)
    result=build(dict(Order=[],OrderLine=[],Product=[]))
    assert all(x['counts']['eligibleCount']==0 and x['records']==[] for x in result['facts'].values())
    assert result['factIds']==[]


def test_large_public_content_is_rejected_without_truncation():
    output=rows()
    output['Product']=[row('Product',i,status='ACTIVE',name='x'*4096) for i in range(1,501)]
    with pytest.raises(ValueError,match='payload limit'):
        build(output)
    assert len(output['Product'])==500 and len(output['Product'][-1]['properties']['name'])==4096


def test_high_cardinality_groups_are_rejected_without_top_n():
    relation,cohort,quality,document=setup()
    next(x for x in document['facts'] if x['objectType']=='Product')['fields'].append(dict(property='bucket',kind='nonnegative-integer'))
    fields=compile_fact_quality_policy(document,relationship_policy=relation,cohort_policy=cohort,quality_policy=quality)
    doc=dict(schemaVersion='aos.snapshot-business-facts/v1',fieldPolicyHash=fields.content_hash,purposeCode=fields.purpose_code,
        facts=[dict(objectType=ot,mode='group-counts' if ot=='Product' else 'records',fields=['bucket'] if ot=='Product' else ['name'])
            for ot in relation.object_types])
    policy=compile_business_fact_policy(doc,field_policy=fields)
    output=rows();output['Product']=[row('Product',i,status='ACTIVE',name='public',bucket=i) for i in range(1,258)]
    with pytest.raises(ValueError,match='group limit'):
        build_business_facts(output,relation,cohort,quality,fields,policy,window_start=START,window_end=END,observed_at=END)
    assert len(output['Product'])==257
