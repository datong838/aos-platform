import importlib
import pytest
from test_growth19_successor_business import profile


@pytest.mark.parametrize('phase', ['approve', 'disable'])
def test_existing_pause_intent_prevents_resend(profile, monkeypatch, tmp_path, phase):
    module = importlib.import_module('a0v_event_complete_g_pause')
    monkeypatch.setattr(module, 'STATE', tmp_path)
    (tmp_path / (phase + '-intent.json')).write_text('{}')
    calls = []
    monkeypatch.setattr(module.g, 'setup', lambda: calls.append('setup'))
    with pytest.raises(ValueError, match='read-only inspection'):
        module.run(phase)
    assert calls == []
