import importlib
import pytest
from test_growth19_successor_business import profile


@pytest.mark.parametrize('phase',['approve-disable','disable','approve-fence','fence','approve-shrink','shrink','shrink-recovered'])
def test_retirement_unknown_outcome_never_resends(profile,monkeypatch,tmp_path,phase):
    m=importlib.import_module('a0v_event_complete_f_retirement')
    monkeypatch.setattr(m,'STATE',tmp_path);(tmp_path/(phase+'-intent.json')).write_text('{}')
    calls=[];monkeypatch.setattr(m.f,'setup',lambda:calls.append('setup'))
    with pytest.raises(ValueError,match='read-only'):m.run(phase)
    assert calls==[]
