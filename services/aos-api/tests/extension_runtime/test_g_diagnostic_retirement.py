import importlib
import pytest
from test_growth19_successor_business import profile


@pytest.mark.parametrize('phase',['approve-fence','fence','approve-shrink','shrink'])
def test_g_retirement_never_resends(profile,monkeypatch,tmp_path,phase):
    m=importlib.import_module('a0v_g_diagnostic_retirement');monkeypatch.setattr(m,'STATE',tmp_path)
    (tmp_path/(phase+'-intent.json')).write_text('{}')
    monkeypatch.setattr(m.f,'setup',lambda:pytest.fail('unknown outcome resent'))
    with pytest.raises(ValueError,match='read-only'):m.run(phase)


def test_g_retirement_cannot_repeat_disable_or_use_f_recovery(profile):
    m=importlib.import_module('a0v_g_diagnostic_retirement')
    for phase in ('disable','approve-disable','shrink-recovered'):
        with pytest.raises(ValueError,match='only exact G'):m.run(phase)
