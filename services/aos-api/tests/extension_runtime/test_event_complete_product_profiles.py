import importlib
import pytest
from test_event_complete_successor_business import profile

@pytest.mark.parametrize('fault',[None,'old','generation','revision','config','unresumed'])
def test_f_preflight_keeps_current_identity_and_resume_requirement(profile,fault):
    f,s,_=profile;p=importlib.import_module('a0v_event_complete_product_preflight').load_profile()
    create=dict(installationId=f.G_ID,installationState='approved');b=s['bindings'][0];b['revision']=6
    resumed=True
    if fault=='old':create['installationId']='old-e'
    elif fault=='generation':b['generation']='old-e'
    elif fault=='revision':b['revision']=4
    elif fault=='config':b['config_ref']['revision']=2
    elif fault=='unresumed':resumed=False
    if fault:
        with pytest.raises(ValueError):p.require_current_head(create,s['head'],b,resumed)
    else:assert p.require_current_head(create,s['head'],b,resumed)['installationId']==f.G_ID
    assert '/g/create-result.json' in str(p.CURRENT_CREATE)
    assert p.BUNDLE_ROOT.name=='signed-bundles-event-complete'


@pytest.mark.parametrize('module,phase',[
 ('authority','prepare'),('authority','selection'),('authority','control'),('authority','binding'),
 ('policy','prepare'),('policy','approve'),('policy','put'),
 ('enable','approve-dispatch'),('enable','expand'),('enable','approve-control'),('enable','enable')])
def test_g_profiles_never_retry_existing_intent(profile,monkeypatch,tmp_path,module,phase):
    m=importlib.import_module('a0v_event_complete_product_'+module)
    monkeypatch.setattr(m,'STATE',tmp_path);(tmp_path/(phase+'-intent.json')).write_text('{}')
    with pytest.raises(ValueError,match='read-only'):m.run(phase,object())


def test_g_source_uses_current_successor_and_never_repeats_unknown_run(profile,monkeypatch,tmp_path):
    m=importlib.import_module('a0v_event_complete_product_source_once')
    assert m.authority_profile().f.G_ID==profile[0].G_ID
    assert m.policy_profile().f.G_ID==profile[0].G_ID
    monkeypatch.setattr(m,'STATE',tmp_path);(tmp_path/'execute-intent.json').write_text('{}')
    monkeypatch.setattr(m.f,'setup',lambda:pytest.fail('unknown outcome attempted execution'))
    with pytest.raises(ValueError,match='read-only'):m.run()
