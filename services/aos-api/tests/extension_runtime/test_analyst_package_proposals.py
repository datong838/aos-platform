"""Domain DTO parity and isolated imports, never business authority proof."""
import importlib
import json
from pathlib import Path
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[4]
BACKEND = ROOT / 'bundles/solutions/ecommerce-growth/backend'

@pytest.fixture
def parsers(monkeypatch):
    monkeypatch.syspath_prepend(str(BACKEND))
    from aos_api import ecommerce_analyst_analysis_proposal as ha
    from aos_api import ecommerce_analyst_growth_plan_draft as hg
    ba = importlib.import_module('ecommerce_growth.ecommerce_analyst_analysis_proposal')
    bg = importlib.import_module('ecommerce_growth.ecommerce_analyst_growth_plan_draft')
    return ha,hg,ba,bg

def sample(stage):
    if stage == 'portrait':
        return dict(summary='商品来源待核查', assumptions=[], uncertainty='未验证经营效果', sourceIndices=[0], metricIndices=[0])
    if stage == 'diagnosis':
        return dict(conclusion='先补数据缺口', attributionPath=['来源0'], keyAssumptions=[], counterEvidence=[], alternativeExplanations=[], uncertainty='不能证明因果', sourceIndices=[0])
    return dict(objective='内部商品介绍准备', constraints=[], expectedEffect='待人工评审', confidence=0.5, stopConditions=['来源失效'], items=[dict(title='介绍草稿', objective='核对商品字段', sourceIndices=[0])])

def calls(parsers, stage):
    ha,hg,ba,bg=parsers
    if stage=='portrait': return ha.parse_portrait_answer,ba.parse_portrait_answer,dict(source_count=1,metric_count=1)
    if stage=='diagnosis': return ha.parse_diagnosis_answer,ba.parse_diagnosis_answer,dict(source_count=1)
    return hg.parse_growth_plan_answer,bg.parse_growth_plan_answer,dict(source_count=1)

@pytest.mark.parametrize('stage',['portrait','diagnosis','growth'])
def test_schema_and_serialized_contract_parity(parsers,stage):
    old,new,kwargs=calls(parsers,stage)
    raw=json.dumps(sample(stage),ensure_ascii=False)
    a,b=old(raw,**kwargs),new(raw,**kwargs)
    assert type(a).model_json_schema()==type(b).model_json_schema()
    assert a.model_dump(mode='json',by_alias=True)==b.model_dump(mode='json',by_alias=True)

@pytest.mark.parametrize('stage',['portrait','diagnosis','growth'])
@pytest.mark.parametrize('attack',['authority','duplicate','nan','oversize','boolean_index','missing_source','duplicate_index','markdown','array','deep'])
def test_rejects_untrusted_authority_and_malformed_answers(parsers,stage,attack):
    body=sample(stage)
    if attack=='authority': body['approvedAt']='now'
    target=body['items'][0] if stage=='growth' else body
    if attack=='boolean_index': target['sourceIndices']=[True]
    if attack=='missing_source': target['sourceIndices']=[1]
    if attack=='duplicate_index': target['sourceIndices']=[0,0]
    raw=json.dumps(body)
    if attack=='duplicate': raw=raw[:-1]+', "objective": "a", "objective": "b"}'
    if attack=='nan': raw='NaN'
    if attack=='oversize': raw='中'*44000
    if attack=='markdown': raw='```json\n'+raw+'\n```'
    if attack=='array': raw='[]'
    if attack=='deep': raw='['*2000
    old,new,kwargs=calls(parsers,stage)
    for parse in (old,new):
        with pytest.raises(ValueError): parse(raw,**kwargs)

def test_standalone_import_has_no_platform_dependency():
    program='''
import sys
class DenyPlatform:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "aos_api" or fullname.startswith("aos_api."):
            raise AssertionError("platform import forbidden: " + fullname)
sys.meta_path.insert(0, DenyPlatform())
sys.path.insert(0, sys.argv[1])
from ecommerce_growth.ecommerce_analyst_analysis_proposal import parse_portrait_answer
from ecommerce_growth.ecommerce_analyst_growth_plan_draft import parse_growth_plan_answer
from ecommerce_growth.analyst_structure_eval import evaluate_structure
assert not any(k.startswith("aos_api") for k in sys.modules)
'''
    subprocess.run([sys.executable,'-I','-c',program,str(BACKEND)],check=True,capture_output=True,text=True)
