import importlib
import pytest
from test_growth19_successor_business import profile

@pytest.mark.parametrize('phase',['action','approve-dispatch','expand','approve-control','enable'])
def test_no_duplicate_commands_after_unknown_enable_outcome(profile,monkeypatch,tmp_path,phase):
    p=importlib.import_module('a0v_growth19_product_event_enable');monkeypatch.setattr(p,'STATE',tmp_path)
    (tmp_path/(phase+'-intent.json')).write_text('{}')
    with pytest.raises(ValueError,match='read-only'):p.run(phase,object())
