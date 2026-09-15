import importlib
import pytest
from test_growth19_successor_business import profile

@pytest.mark.parametrize('fault',[None,'old','generation','revision','config','unresumed'])
def test_f_preflight_keeps_current_identity_and_resume_requirement(profile,fault):
    f,s,_=profile;p=importlib.import_module('a0v_growth19_product_preflight').load_profile()
    create=dict(installationId=f.F_ID,installationState='approved');b=s['bindings'][0];b['revision']=6
    resumed=True
    if fault=='old':create['installationId']='old-e'
    elif fault=='generation':b['generation']='old-e'
    elif fault=='revision':b['revision']=4
    elif fault=='config':b['config_ref']['revision']=2
    elif fault=='unresumed':resumed=False
    if fault:
        with pytest.raises(ValueError):p.require_current_head(create,s['head'],b,resumed)
    else:assert p.require_current_head(create,s['head'],b,resumed)['installationId']==f.F_ID
    assert '/f/create-result.json' in str(p.CURRENT_CREATE)
    assert p.BUNDLE_ROOT.name=='signed-bundles-growth-1.9-current'
