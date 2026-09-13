import importlib
from copy import deepcopy
from pathlib import Path
import pytest
from tests.test_ecommerce_business_investigation_case import case_payload, successor
from tests.test_ecommerce_business_investigation_run import run_payload
from aos_api.ecommerce_business_investigation_case import BusinessInvestigationCaseRevision
from aos_api.ecommerce_business_investigation_run import BusinessInvestigationRunRecord, BusinessInvestigationRunStateRevision

@pytest.fixture
def projector(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[4]/'packages/aos-extension-sdk/python'))
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[4]/'bundles/solutions/ecommerce-growth/backend'))
    return importlib.import_module('ecommerce_growth.analyst_workspace_view').project_workspace


def snapshot():
    case=successor(BusinessInvestigationCaseRevision.model_validate(case_payload()),'ACTIVE').model_dump(by_alias=True,mode='json')
    ref=dict(resourceType='BusinessInvestigationCaseRevision',resourceId=case['caseId'],revision=case['revision'],contentHash=case['contentHash'])
    run=BusinessInvestigationRunRecord.model_validate(run_payload(caseRef=ref)).model_dump(by_alias=True,mode='json')
    state=BusinessInvestigationRunStateRevision.model_validate(dict(tenant=case['tenant'],runId=run['runId'],version=1,eventSequence=1,
        lifecycle='PREPARING',control='RUNNING',contentHash='sha256:'+'a'*64,createdBy='owner',createdAt=case['createdAt']))
    state=state.model_copy(update={'content_hash':state.calculated_content_hash()}).model_dump(by_alias=True,mode='json')
    return dict(schemaVersion='aos.analyst-workspace-snapshot/v1',tenant=case['tenant'],cutoffAt=case['createdAt'],cases=[dict(case=case,runs=[dict(authority=run,state=state)])],truncated=False)


def test_projects_canonical_refs_without_claiming_business_completion(projector):
    source=snapshot(); original=deepcopy(source); result=projector(source)
    assert source == original
    item=result['cases'][0]
    assert item['caseRef']['contentHash']==source['cases'][0]['case']['contentHash']
    assert item['runs'][0]['runRef']['contentHash']==source['cases'][0]['runs'][0]['authority']['contentHash']
    assert item['runs'][0]['control']=='RUNNING' and result['executionAllowed'] is False
    assert 'createdBy' not in str(result) and 'triggerKey' not in str(result)
    assert 'completed' not in result


@pytest.mark.parametrize('drift',['hash','tenant','run-link','state-link','duplicate-case','duplicate-run','extra-envelope','case-ref-hash'])
def test_mixed_or_tampered_sources_rejected(projector,drift):
    value=snapshot()
    if drift=='hash':value['cases'][0]['case']['title']='changed'
    if drift=='tenant':value['tenant']={'orgId':'dev-org','projectId':'dev-project'}
    if drift=='run-link':value['cases'][0]['runs'][0]['authority']['caseRef']['resourceId']='other'
    if drift=='state-link':value['cases'][0]['runs'][0]['state']['runId']='other'
    if drift=='duplicate-case':value['cases']*=2
    if drift=='duplicate-run':value['cases'][0]['runs']*=2
    if drift=='extra-envelope':value['approved']=True
    if drift=='case-ref-hash':value['cases'][0]['runs'][0]['authority']['caseRef']['contentHash']='sha256:'+'b'*64
    if drift in {'run-link','state-link','case-ref-hash'}:
        import json,hashlib
        row=value['cases'][0]['runs'][0]['state' if drift=='state-link' else 'authority']
        row['contentHash']='sha256:'+hashlib.sha256(json.dumps({k:v for k,v in row.items() if k!='contentHash'},ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    with pytest.raises(ValueError):projector(value)


def test_empty_is_honest_and_never_invents_tasks(projector):
    value=snapshot();value['cases']=[]
    result=projector(value)
    assert result['cases']==[] and result['caseCount']==0 and result['runCount']==0
