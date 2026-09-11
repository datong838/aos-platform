import importlib
import json
import pytest
from test_analyst_package_proposals import BACKEND
from aos_api.ecommerce_analyst_portrait_generation import portrait_prompt
from aos_api.ecommerce_analyst_diagnosis_generation import diagnosis_prompt
from aos_api.ecommerce_analyst_growth_plan_draft import growth_plan_prompt
from test_ecommerce_analyst_portrait_generation import fixture as portrait_fixture
from test_ecommerce_analyst_diagnosis_generation import fixture as diagnosis_fixture
from test_ecommerce_analyst_growth_plan_draft import generation

@pytest.fixture
def build(monkeypatch):
    monkeypatch.syspath_prepend(str(BACKEND))
    return importlib.import_module('ecommerce_growth.analyst_structure_case').structure_case_from_query


def query(monkeypatch,stage):
    if stage=='portrait': return portrait_prompt(**portrait_fixture(monkeypatch))[0]
    if stage=='diagnosis':
        insight,materials,_,_=diagnosis_fixture()
        return diagnosis_prompt(insight,materials)[0]
    decision,_,_=generation()
    return growth_plan_prompt(decision,budget='0',task_type='content')[0]

@pytest.mark.parametrize('stage',['portrait','diagnosis','solution-design'])
def test_actual_prompt_derives_inventory_without_manual_counts(build,monkeypatch,stage):
    raw=query(monkeypatch,stage); payload=json.loads(raw)
    value=build(raw,stage=stage)
    assert value['stage']==stage
    expected=payload['sources'] if stage=='solution-design' else [s['bundleRef'] for s in payload['sources']]
    assert value['sourceRefs']==expected
    assert value['metricSources']==([[0]] if stage=='portrait' else [])
    assert 'summary' not in json.dumps(value)

@pytest.mark.parametrize('stage',['portrait','diagnosis','solution-design'])
@pytest.mark.parametrize('fault',['protocol','sources','extra','duplicate','oversize','wrong_stage'])
def test_malformed_generation_context_rejected(build,monkeypatch,stage,fault):
    payload=json.loads(query(monkeypatch,stage))
    if fault=='protocol':payload['protocol']='unknown'
    if fault=='sources':payload['sources']=[]
    if fault=='extra':payload['sourceCount']=1
    raw=json.dumps(payload)
    if fault=='duplicate':raw=raw[:-1]+',"protocol":"bad"}'
    if fault=='oversize':raw='x'*16001
    if fault=='wrong_stage':stage='unknown'
    with pytest.raises(ValueError,match='INVALID_GENERATION_CONTEXT'):build(raw,stage=stage)

@pytest.mark.parametrize('stage',['portrait','diagnosis'])
def test_original_evidence_body_hash_is_checked(build,monkeypatch,stage):
    payload=json.loads(query(monkeypatch,stage));payload['sources'][0]['items'][0]['payload']['secret']='DO_NOT_ECHO'
    with pytest.raises(ValueError) as exc:build(json.dumps(payload),stage=stage)
    assert str(exc.value)=='INVALID_GENERATION_CONTEXT'

@pytest.mark.parametrize('fault',['metric_hash','missing_support','duplicate_support'])
def test_portrait_requires_unique_actual_metric_source(build,monkeypatch,fault):
    payload=json.loads(query(monkeypatch,'portrait'))
    if fault=='metric_hash':payload['metrics'][0]['contentHash']='c'*64
    if fault=='missing_support':payload['sources'][0]['items'][0]['payload'].pop('metricDefinitionRef')
    if fault=='duplicate_support':payload['sources'].append(payload['sources'][0])
    with pytest.raises(ValueError,match='INVALID_GENERATION_CONTEXT'):build(json.dumps(payload),stage='portrait')

@pytest.mark.parametrize('stage',['diagnosis','solution-design'])
def test_parent_inventory_must_match_original_order_and_hash(build,monkeypatch,stage):
    payload=json.loads(query(monkeypatch,stage))
    if stage=='diagnosis':payload['sources'][0]['bundleRef']['resourceId']='other'
    else:payload['sources'][0]['resourceId']='other'
    with pytest.raises(ValueError,match='INVALID_GENERATION_CONTEXT'):build(json.dumps(payload),stage=stage)
