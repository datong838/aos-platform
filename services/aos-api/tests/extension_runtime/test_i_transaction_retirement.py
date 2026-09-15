import importlib
import pytest
from test_growth19_successor_business import profile


@pytest.mark.parametrize('phase',['approve-fence','fence','approve-shrink','shrink'])
def test_h_retirement_never_resends(profile,monkeypatch,tmp_path,phase):
    m=importlib.import_module('a0v_i_transaction_retirement');monkeypatch.setattr(m,'STATE',tmp_path)
    (tmp_path/(phase+'-intent.json')).write_text('{}')
    monkeypatch.setattr(m.f,'setup',lambda:pytest.fail('unknown outcome resent'))
    with pytest.raises(ValueError,match='read-only'):m.run(phase)


def test_h_retirement_cannot_repeat_disable_or_use_f_recovery(profile):
    m=importlib.import_module('a0v_i_transaction_retirement')
    for phase in ('disable','approve-disable','shrink-recovered'):
        with pytest.raises(ValueError,match='only exact I'):m.run(phase)


def test_h_retirement_fixed_identity_and_isolated_state(profile):
    m=importlib.import_module('a0v_i_transaction_retirement')
    c=importlib.import_module('a0v_i_unaccepted_analysis_close')
    assert m.f.G_ID=='ef5bc0c3-1dbe-4659-b839-2350f70232bf'
    assert m.f.G_GENERATION=='c26edf1c-5170-4158-9f30-36dc1f2ba07f'
    assert 'successor-i' in str(m.STATE) and m.STATE.name=='transaction-retirement'
    assert c.g.G_ID==m.f.G_ID and 'successor-i' in str(c.STATE)
    assert c.PREFIX=='a0v-i-unaccepted-analysis-20260916'
