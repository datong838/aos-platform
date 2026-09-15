import importlib
import pytest
from test_growth19_successor_business import profile

@pytest.mark.parametrize('phase',['prepare','selection','control','binding'])
def test_existing_authority_intent_never_writes(profile,monkeypatch,tmp_path,phase):
    p=importlib.import_module('a0v_growth19_product_authority');monkeypatch.setattr(p,'STATE',tmp_path)
    (tmp_path/(phase+'-intent.json')).write_text('{}')
    with pytest.raises(ValueError,match='read-only'):p.run(phase,object())

@pytest.mark.parametrize('fault',[None,'installationRef','generation','configurationRef','orgId'])
def test_authority_draft_never_uses_E_or_canary(profile,fault):
    f,_,_=profile;p=importlib.import_module('a0v_growth19_product_authority')
    draft=dict(installationRef=dict(installationId=f.F_ID),generation=f.F_GENERATION,executionEpoch=3,configurationRef=f.CONFIG,pipelineId=p.PIPELINE,orgId='org-org',projectId='dev-project')
    if fault:
        draft[fault]={'installationId':'old-e'} if fault=='installationRef' else 'other'
        with pytest.raises(ValueError):p.require_f(draft)
    else:p.require_f(draft)
