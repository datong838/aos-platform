import importlib
import pytest
from test_growth19_successor_business import profile


def test_step_unknown_never_resends(profile,tmp_path):
    m=importlib.import_module('a0v_firstchain_binding_successor')
    (tmp_path/'create-intent.json').write_text('{}')
    with pytest.raises(ValueError,match='read-only'):
        m.step(tmp_path,'create',{},lambda:pytest.fail('resend'))


def test_skill_proof_requires_all_exact_successor_revisions(profile):
    m=importlib.import_module('a0v_firstchain_binding_successor')
    rows=[{'skill':dict(asset_id='ecommerce.skill.'+x,revision=3,content_hash='a'*64)} for x in m.LOGICS]
    assert len(m.skill_proof({'skills':rows}))==8
    rows[0]['skill']['revision']=2
    with pytest.raises(ValueError):m.skill_proof({'skills':rows})


@pytest.mark.parametrize('phase',['graphs','publication','contracts','bindings','verify'])
def test_main_successor_unknown_never_restarts(profile,tmp_path,monkeypatch,phase):
    m=importlib.import_module('a0v_g_model_successor_apply')
    monkeypatch.setattr(m,'STATE',tmp_path)
    (tmp_path/(phase+'-intent.json')).write_text('{}')
    monkeypatch.setattr(m.g,'setup',lambda:pytest.fail('unknown main operation restarted'))
    with pytest.raises(ValueError,match='read-only'):m.run(phase)
