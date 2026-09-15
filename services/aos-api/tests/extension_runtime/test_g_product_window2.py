import importlib
import pytest
from test_growth19_successor_business import profile


@pytest.mark.parametrize('name,phase',[('authority','prepare'),('policy','prepare'),('enable','approve-control')])
def test_window_profiles_retain_identity_and_no_resend(profile,tmp_path,name,phase):
    m=importlib.import_module('a0v_g_product_window2')
    p=getattr(m,name+'_profile')()
    assert p.STATE.name.endswith('v2')
    p.STATE=tmp_path;(tmp_path/(phase+'-intent.json')).write_text('{}')
    with pytest.raises(ValueError,match='read-only'):p.run(phase,None)


def test_source_window_uses_new_policy_revision(profile):
    m=importlib.import_module('a0v_g_product_window2');p=m.source_profile()
    assert p.POLICY_REVISION==4
    assert p.STATE.name=='product-source-v2'
    assert p.policy_profile().STATE.name=='product-event-v2'
