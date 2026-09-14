from copy import deepcopy
from datetime import datetime,timezone
import pytest
from aos_api.pipeline_snapshot_relationships import compile_relationship_policy,assess_snapshot_relationships


def policy():return {'schemaVersion':'aos.snapshot-relationships/v1','objectTypes':['Order','OrderLine'],'rules':[dict(linkType='Order.lines',rowType='OrderLine',parentType='Order',referenceProperty='orderId',direction='parent-to-row',encoding='positive-id',allowUnset=False)]}
def row(ot,key,**props):return dict(ot=ot,source_pk=str(key),is_deleted=False,properties=props)
def rows():return {'Order':[row('Order',1)],'OrderLine':[row('OrderLine',2,orderId=1)]}
def assess(data=None,definition=None):return assess_snapshot_relationships(rows() if data is None else data,compile_relationship_policy(policy() if definition is None else definition),observed_at=datetime(2026,9,14,tzinfo=timezone.utc))


def test_exact_direction_and_canonical_link():
    result=assess();link=result.candidate_links[0]
    assert link['source_type']=='Order' and link['source_pk']=='1'
    assert link['target_type']=='OrderLine' and link['target_source_pk']=='2'
    assert link['properties']['sourceModificationTimeKnown'] is False
    from aos_api.ec_ot_writer import _normalize_rows
    from aos_api.ecom_core_models import SyncScope
    objects,links=_normalize_rows(list(result.candidate_links),SyncScope(org_id='org-org',workspace_id='dev-project',platform='niushop',shop_or_marketplace_id='1',stream='fixture'))
    assert not objects and len(links)==1

@pytest.mark.parametrize('fault',['extra','unknown_type','duplicate_rule','duplicate_type','bad_direction','bad_bool','bad_encoding'])
def test_invalid_policy_is_rejected(fault):
    d=policy()
    if fault=='extra':d['allowMissing']=True
    elif fault=='unknown_type':d['rules'][0]['parentType']='Other'
    elif fault=='duplicate_rule':d['rules']*=2
    elif fault=='duplicate_type':d['objectTypes']+=['Order']
    elif fault=='bad_direction':d['rules'][0]['direction']='automatic'
    elif fault=='bad_bool':d['rules'][0]['allowUnset']=1
    else:d['rules'][0]['encoding']='guess'
    with pytest.raises(ValueError):compile_relationship_policy(d)

@pytest.mark.parametrize('fault',['missing_type','duplicate_row','link','bad_pk','wrong_ot'])
def test_invalid_cohort_fails_whole_assessment(fault):
    data=rows()
    if fault=='missing_type':data.pop('Order')
    elif fault=='duplicate_row':data['Order']*=2
    elif fault=='link':data['Order'][0]['link_type']='Order.lines'
    elif fault=='bad_pk':data['Order'][0]['source_pk']='01'
    else:data['Order'][0]['ot']='Other'
    with pytest.raises(ValueError):assess(data)

@pytest.mark.parametrize('value,expected',[(None,'missingReference'),(True,'invalidReference'),('01','invalidReference'),(4,'missingParent'),(0,'invalidReference')])
def test_missing_or_invalid_reference_is_reported_not_fabricated(value,expected):
    data=rows();data['OrderLine'][0]['properties']['orderId']=value
    result=assess(data)
    assert not result.candidate_links and result.counts['Order.lines'][expected]==1


def test_deleted_endpoint_never_becomes_implicit_tombstone():
    data=rows();data['Order'][0]['is_deleted']=True
    result=assess(data)
    assert not result.candidate_links and result.counts['Order.lines']['deletedEndpoint']==1


def test_explicit_unset_policy_and_empty_cohort():
    p=policy();p['rules'][0]['allowUnset']=True
    data=rows();data['OrderLine'][0]['properties']['orderId']=0
    assert assess(data,p).counts['Order.lines']['allowedUnset']==1
    assert not assess({'Order':[],'OrderLine':[]}).candidate_links

@pytest.mark.parametrize('value,valid',[(',1,',True),('1',False),(',1,,',False),(',01,',False),(',1,1,',False),(', 1,',False)])
def test_explicit_wrapped_encoding(value,valid):
    p=policy();p['rules'][0]['encoding']='wrapped-csv-positive-id'
    data=rows();data['OrderLine'][0]['properties']['orderId']=value
    assert len(assess(data,p).candidate_links)==int(valid)


def test_policy_is_frozen_against_caller_mutation():
    p=policy();compiled=compile_relationship_policy(p);before=compiled.content_hash
    p['rules'][0]['referenceProperty']='secret'
    result=assess_snapshot_relationships(rows(),compiled,observed_at=datetime.now(timezone.utc))
    assert len(result.candidate_links)==1 and result.policy_hash==before


def test_manually_rebound_policy_hash_is_rejected():
    from dataclasses import replace
    compiled=replace(compile_relationship_policy(policy()),content_hash='sha256:'+'f'*64)
    with pytest.raises(ValueError):assess_snapshot_relationships(rows(),compiled,observed_at=datetime.now(timezone.utc))


def test_total_candidates_are_bounded():
    p=policy();original=p['rules'][0]
    p['rules']=[original|{'linkType':'Order.test'+str(i)} for i in range(32)]
    data=rows();data['OrderLine']=[row('OrderLine',i,orderId=1) for i in range(1,1000)]
    with pytest.raises(ValueError,match='limit exceeded'):assess(data,p)


def test_reference_list_is_bounded_and_not_partially_accepted():
    p=policy();p['rules'][0]['encoding']='csv-positive-id'
    data=rows();data['OrderLine'][0]['properties']['orderId']=','.join(str(i) for i in range(1,34))
    result=assess(data,p)
    assert not result.candidate_links and result.counts['Order.lines']['invalidReference']==1


def retirement_policy():
    return policy() | {'schemaVersion':'aos.snapshot-relationships/v2', 'retirement': {
        'mode':'present-rows-only', 'requireCompleteReferences':True,
        'rejectNewerThanObservation':True, 'allowMissingRowDeletion':False}}


def test_retirement_requires_explicit_versioned_policy():
    assert compile_relationship_policy(policy()).retirement_mode == 'disabled'
    compiled = compile_relationship_policy(retirement_policy())
    assert compiled.retirement_mode == 'present-rows-only'
    assert len(assess(definition=retirement_policy()).candidate_links) == 1
    assert not any(link['is_deleted'] for link in assess(definition=retirement_policy()).candidate_links)


@pytest.mark.parametrize('fault', ['missing', 'mode', 'missing_rows', 'incomplete', 'future', 'numeric_bool', 'extra'])
def test_retirement_policy_cannot_relax_required_boundaries(fault):
    definition = retirement_policy()
    if fault == 'missing': definition.pop('retirement')
    elif fault == 'mode': definition['retirement']['mode'] = 'all-absent-links'
    elif fault == 'missing_rows': definition['retirement']['allowMissingRowDeletion'] = True
    elif fault == 'incomplete': definition['retirement']['requireCompleteReferences'] = False
    elif fault == 'future': definition['retirement']['rejectNewerThanObservation'] = False
    elif fault == 'numeric_bool': definition['retirement']['rejectNewerThanObservation'] = 1
    else: definition['retirement']['skipApproval'] = True
    with pytest.raises(ValueError): compile_relationship_policy(definition)


def test_forged_retirement_mode_cannot_keep_original_policy_hash():
    from dataclasses import replace
    original = compile_relationship_policy(policy())
    forged = replace(original, retirement_mode='present-rows-only')
    with pytest.raises(ValueError):
        assess_snapshot_relationships(rows(), forged, observed_at=datetime.now(timezone.utc))
