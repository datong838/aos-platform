import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[4]

def module():
    spec=importlib.util.spec_from_file_location('niushop_config_profile',ROOT/'scripts/a0v_niushop_1_5_configure.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def test_new_profile_preserves_original_configuration_target(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    m=module();profile=m.load_profile()
    target=profile.configuration_target()
    assert target[0]=='eda57424-b8cb-401e-a6f7-94220cb4f9ef'
    assert 'niushop-1.5-replacement' in str(target[1])
    assert 'signed-bundles-niushop-1.5' in str(profile.BUNDLE_ROOT)
    import a0v_ecommerce_1_7_configure as original
    assert original.configuration_target()[0]=='e42e042b-1fe7-4cfa-bb83-469ff256081d'

@pytest.mark.parametrize('flag',['recovery','sleep_recovery','niushop_1_4'])
def test_new_profile_rejects_other_recovery_targets(monkeypatch,flag):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    with pytest.raises(ValueError):module().load_profile().configuration_target(**{flag:True})


def test_configuration_unknown_outcome_cannot_resend(monkeypatch,tmp_path):
    from types import SimpleNamespace
    from unittest.mock import Mock
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    m=module();monkeypatch.setattr(m,'STATE',tmp_path)
    request=Mock(side_effect=RuntimeError('unknown outcome'))
    monkeypatch.setattr(m,'load_profile',lambda:SimpleNamespace(run=request))
    with pytest.raises(RuntimeError):m.run('configure')
    with pytest.raises(FileExistsError):m.run('configure')
    assert request.call_count==1


def test_preflight_creates_no_mutation_intent(monkeypatch,tmp_path):
    from types import SimpleNamespace
    m=module();monkeypatch.setattr(m,'STATE',tmp_path)
    monkeypatch.setattr(m,'load_profile',lambda:SimpleNamespace(run=lambda action:action))
    assert m.run('preflight')=='preflight'
    assert not list(tmp_path.iterdir())
