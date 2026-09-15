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


def test_renewal_preserves_original_state_and_requires_exact_private_predecessors(profile,monkeypatch,tmp_path):
    import json
    f,_,_=profile;monkeypatch.setattr(f,'STATE',tmp_path)
    p=importlib.import_module('a0v_growth19_product_authority_renewal').load_profile()
    assert p.STATE==tmp_path/'product-authority-v2'
    with pytest.raises(ValueError,match='predecessor'):p.previous_reference('selection')
    original=tmp_path/'product-authority';original.mkdir()
    path=original/'selection-result.json';path.write_text(json.dumps({'ref':{'resourceId':'original-selection','revision':1}}));path.chmod(0o600)
    assert p.previous_reference('selection')=={'resourceId':'original-selection','revision':1}
    event=importlib.import_module('a0v_growth19_product_event_policy_renewal').load_profile()
    assert event.authority.STATE==p.STATE
    assert event.STATE==tmp_path/'product-event-v2'


def test_third_window_rejects_unreceipted_or_mismatched_policy(profile,monkeypatch,tmp_path):
    import json
    f,_,_=profile;monkeypatch.setattr(f,'STATE',tmp_path)
    p=importlib.import_module('a0v_growth19_product_event_policy_window3').load_profile()
    assert p.authority.STATE==tmp_path/'product-authority-v3'
    assert p.STATE==tmp_path/'product-event-v3'
    with pytest.raises(ValueError,match='predecessor'):p.previous_policy_payload()
    old=tmp_path/'product-event-v2';old.mkdir()
    policy={'revision':1,'contentHash':'sha256:old'}
    for phase,value in [('prepare',{'command':{'policy':policy}}),('put',{'receiptRef':{'resourceId':p.POLICY,'revision':2,'contentHash':'sha256:old'}})]:
        path=old/(phase+'-result.json');path.write_text(json.dumps(value));path.chmod(0o600)
    with pytest.raises(ValueError,match='differs'):p.previous_policy_payload()
    path=old/'put-result.json';path.write_text(json.dumps({'receiptRef':{'resourceId':p.POLICY,'revision':1,'contentHash':'sha256:old'}}))
    assert p.previous_policy_payload()['tenant']=={'orgId':'org-org','projectId':'dev-project'}
    enable=importlib.import_module('a0v_growth19_product_event_enable_window3').load_profile()
    assert enable.STATE==tmp_path/'event-enable-v3'
    assert enable.policy_profile().STATE==p.STATE
