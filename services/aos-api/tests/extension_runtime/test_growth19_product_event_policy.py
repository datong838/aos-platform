import importlib
import pytest
from test_growth19_successor_business import profile

@pytest.mark.parametrize('phase',['prepare','approve','put'])
def test_policy_unknown_phase_does_not_resubmit(profile,monkeypatch,tmp_path,phase):
    p=importlib.import_module('a0v_growth19_product_event_policy');monkeypatch.setattr(p,'STATE',tmp_path)
    (tmp_path/(phase+'-intent.json')).write_text('{}')
    with pytest.raises(ValueError,match='read-only'):p.run(phase,object())
    assert p.POLICY!='product-event-qyh-full-store-baseline-20260915'
    assert p.CASE=='case-qyh-full-store-baseline-20260915'
