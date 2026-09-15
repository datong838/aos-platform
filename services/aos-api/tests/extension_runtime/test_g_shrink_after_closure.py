import importlib
import pytest
from test_growth19_successor_business import profile


def test_unknown_recovery_intent_never_resends(profile,monkeypatch,tmp_path):
    m=importlib.import_module('a0v_g_shrink_after_closure');monkeypatch.setattr(m,'STATE',tmp_path)
    (tmp_path/'recovery-intent.json').write_text('{}')
    monkeypatch.setattr(m.g,'setup',lambda:pytest.fail('must inspect prior intent'))
    with pytest.raises(ValueError,match='readback'):m.run()


@pytest.mark.parametrize('receipts,pending,existing',[(20,0,0),(21,1,0),(21,0,1)])
def test_incomplete_proof_rejected(profile,receipts,pending,existing):
    m=importlib.import_module('a0v_g_shrink_after_closure')
    with pytest.raises(ValueError):m.require_counts(receipts=receipts,unresolved=pending,existing=existing)


@pytest.mark.parametrize('phase',['approve','shrink'])
def test_renewal_retains_unknown_intent(profile,monkeypatch,tmp_path,phase):
    m=importlib.import_module('a0v_g_retirement_approval_renewal');monkeypatch.setattr(m,'STATE',tmp_path)
    (tmp_path/(phase+'-intent.json')).write_text('{}')
    monkeypatch.setattr(m.g,'setup',lambda:pytest.fail('unknown renewal must not be resent'))
    with pytest.raises(ValueError,match='readback'):m.run(phase)
