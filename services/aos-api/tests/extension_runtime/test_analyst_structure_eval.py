import copy
import hashlib
import importlib
import json
import pytest
from test_analyst_package_proposals import BACKEND, sample

@pytest.fixture
def evaluate(monkeypatch):
    monkeypatch.syspath_prepend(str(BACKEND))
    return importlib.import_module('ecommerce_growth.analyst_structure_eval').evaluate_structure

def envelope(stage='portrait'):
    body=json.dumps(sample('growth' if stage=='solution-design' else stage),ensure_ascii=False)
    source=dict(resourceType='EvidenceBundleRevision',resourceId='source-1',revision=1,contentHash='a'*64)
    case=dict(schemaVersion='aos.analyst-structure-case/v1',stage=stage,sourceRefs=[source],metricSources=[[0]] if stage=='portrait' else [])
    return dict(schemaVersion='aos.eval-text-subject-input/v1',subjectText=body,subjectArtifactRef=dict(resourceType='Artifact',resourceId='text-1',contentHash=hashlib.sha256(body.encode()).hexdigest()),caseInput=case)

def replace_body(item,payload):
    item['subjectText']=json.dumps(payload,ensure_ascii=False)
    item['subjectArtifactRef']['contentHash']=hashlib.sha256(item['subjectText'].encode()).hexdigest()

@pytest.mark.parametrize('stage',['portrait','diagnosis','solution-design'])
def test_actual_body_valid_structure_only(evaluate,stage):
    item=envelope(stage); before=copy.deepcopy(item)
    assert evaluate(item)==dict(schemaVersion='aos.analyst-structure-result/v1',stage=stage,structurePassed=True,detailCode='STRUCTURE_VALID')
    assert item==before

@pytest.mark.parametrize('stage',['portrait','diagnosis','solution-design'])
def test_invalid_answer_returns_fixed_code_without_text(evaluate,stage):
    item=envelope(stage); replace_body(item,{'secretBusinessText':'DO_NOT_ECHO','approvedAt':'today'})
    result=evaluate(item)
    assert result['structurePassed'] is False
    assert result['detailCode']=='ANSWER_STRUCTURE_INVALID'
    assert 'DO_NOT_ECHO' not in json.dumps(result)

@pytest.mark.parametrize('change',['protocol','body','scope','case_protocol','stage','duplicate_source','bool_revision','hash','mapping','bool_index','no_sources','extra','nonportrait_mapping'])
def test_invalid_input_cannot_be_counted_as_structural_pass(evaluate,change):
    item=envelope()
    if change=='protocol': item['schemaVersion']='unknown'
    if change=='body': item['subjectText']+='x'
    if change=='scope': item['subjectArtifactRef']['tenant']='injected'
    if change=='case_protocol': item['caseInput']['schemaVersion']='unknown'
    if change=='stage': item['caseInput']['stage']='solution_design'
    if change=='duplicate_source': item['caseInput']['sourceRefs']*=2
    if change=='bool_revision': item['caseInput']['sourceRefs'][0]['revision']=True
    if change=='hash': item['caseInput']['sourceRefs'][0]['contentHash']='wrong'
    if change=='mapping': item['caseInput']['metricSources']=[[1]]
    if change=='bool_index': item['caseInput']['metricSources']=[[True]]
    if change=='no_sources': item['caseInput']['sourceRefs']=[]
    if change=='extra': item['caseInput']['approved']=True
    if change=='nonportrait_mapping': item['caseInput']['stage']='diagnosis'
    with pytest.raises(ValueError,match='INVALID_STRUCTURE_INPUT'): evaluate(item)

def test_portrait_selected_metric_must_have_selected_source(evaluate):
    item=envelope()
    second=copy.deepcopy(item['caseInput']['sourceRefs'][0]); second['resourceId']='source-2'
    item['caseInput']['sourceRefs'].append(second)
    item['caseInput']['metricSources']=[[1]]
    assert evaluate(item)['detailCode']=='METRIC_SOURCE_NOT_SELECTED'
    body=sample('portrait'); body['sourceIndices']=[1]; replace_body(item,body)
    assert evaluate(item)['structurePassed'] is True


def test_metric_requiring_multiple_sources_cannot_keep_only_one(evaluate):
    item=envelope()
    second=copy.deepcopy(item['caseInput']['sourceRefs'][0]); second['resourceId']='source-2'
    item['caseInput']['sourceRefs'].append(second)
    item['caseInput']['metricSources']=[[0,1]]
    assert evaluate(item)['detailCode']=='METRIC_SOURCE_NOT_SELECTED'
    body=sample('portrait'); body['sourceIndices']=[0,1]; replace_body(item,body)
    assert evaluate(item)['structurePassed'] is True


def test_invalid_input_exception_does_not_echo_original_text(evaluate):
    item=envelope(); item['subjectText']={'DO_NOT_ECHO':'secret'}
    with pytest.raises(ValueError) as error: evaluate(item)
    assert str(error.value)=='INVALID_STRUCTURE_INPUT'
