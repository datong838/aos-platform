import importlib
import pytest
from test_growth19_successor_business import profile

@pytest.mark.parametrize('phase',['prepare','approve','put','put-recovered'])
def test_policy_unknown_phase_does_not_resubmit(profile,monkeypatch,tmp_path,phase):
    p=importlib.import_module('a0v_growth19_product_event_policy');monkeypatch.setattr(p,'STATE',tmp_path)
    (tmp_path/(phase+'-intent.json')).write_text('{}')
    with pytest.raises(ValueError,match='read-only'):p.run(phase,object())
    assert p.POLICY!='product-event-qyh-full-store-baseline-20260915'
    assert p.CASE=='case-qyh-full-store-baseline-20260915'


@pytest.mark.parametrize('fault',[None,'policy','receipt','case'])
def test_only_proven_absent_save_may_recover(profile,fault):
    p=importlib.import_module('a0v_growth19_product_event_policy')
    proof=dict(policyCount=0,receiptCount=0,case=dict(current_revision=2,version=2,lifecycle='ACTIVE'))
    if fault=='policy':proof['policyCount']=1
    elif fault=='receipt':proof['receiptCount']=1
    elif fault=='case':proof['case']['current_revision']=3
    if fault:
        with pytest.raises(ValueError,match='proven absent'):p.require_empty_failed_put(proof,2)
    else:p.require_empty_failed_put(proof,2)
