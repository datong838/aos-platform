import importlib
import pytest
from test_growth19_successor_business import profile


@pytest.mark.parametrize('phase',['approve-fence','fence','approve-shrink','shrink'])
def test_h_retirement_never_resends(profile,monkeypatch,tmp_path,phase):
    m=importlib.import_module('a0v_h_bootstrap_retirement');monkeypatch.setattr(m,'STATE',tmp_path)
    (tmp_path/(phase+'-intent.json')).write_text('{}')
    monkeypatch.setattr(m.f,'setup',lambda:pytest.fail('unknown outcome resent'))
    with pytest.raises(ValueError,match='read-only'):m.run(phase)


def test_h_retirement_cannot_repeat_disable_or_use_f_recovery(profile):
    m=importlib.import_module('a0v_h_bootstrap_retirement')
    for phase in ('disable','approve-disable','shrink-recovered'):
        with pytest.raises(ValueError,match='only exact H'):m.run(phase)


def test_h_retirement_fixed_identity_and_isolated_state(profile):
    m=importlib.import_module('a0v_h_bootstrap_retirement')
    c=importlib.import_module('a0v_h_unaccepted_analysis_close')
    assert m.f.G_ID=='1cc13337-c1de-40a7-b45e-acb41f20a19b'
    assert m.f.G_GENERATION=='ba5d7266-5e7e-454f-85c0-04709305592f'
    assert 'successor-h' in str(m.STATE) and m.STATE.name=='bootstrap-retirement'
    assert c.g.G_ID==m.f.G_ID and 'successor-h' in str(c.STATE)
    assert c.PREFIX=='a0v-h-unaccepted-analysis-20260916'
