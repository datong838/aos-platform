"""Historical T attempt keeps the real failed S/T ordering reproducible."""
import importlib.util
from pathlib import Path
import pytest


PATH=Path(__file__).resolve().parents[4]/'scripts/a0v_t_replacement_install.py'
SPEC=importlib.util.spec_from_file_location('a0v_t_replacement_install',PATH)
replacement=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(replacement)


def test_fixed_t_sequence_and_versions():
    assert replacement.ACTIONS==('preflight','create-t','uninstall-s','prepare-t','verify-t',
        'stage-t','configure-t','enable-t','observe')
    assert replacement.VERSIONS=={'domain.ecommerce.core':'1.4.0',
        'platform.ecommerce.niushop':'1.23.0','solution.ecommerce.growth':'1.10.0',
        'solution.ecommerce.operations-base':'1.2.0'}
    assert replacement.S_DISABLE_OPERATION=='5243452a-161c-40cb-aa9c-6dc5dd8f544b'


def test_unknown_action_fails_before_profile(monkeypatch):
    monkeypatch.setattr(replacement,'load_profile',lambda:pytest.fail('must not load profile'))
    with pytest.raises(ValueError,match='unsupported T replacement action'):
        replacement.run('retry')


def test_historical_failed_writes_are_sealed_before_profile(monkeypatch):
    monkeypatch.setattr(replacement,'load_profile',lambda:pytest.fail('must not load profile'))
    with pytest.raises(ValueError,match='historical failed T attempt is sealed'):
        replacement.run('prepare-t')


def test_initial_accepts_only_private_canonical_t(tmp_path,monkeypatch):
    monkeypatch.setattr(replacement,'STATE',tmp_path);monkeypatch.setattr(replacement,'T_DIR',tmp_path/'t')
    profile=replacement.load_profile()
    with pytest.raises(ValueError,match='only fixed T'):
        profile._initial('s')
    (tmp_path/'t').mkdir();(tmp_path/'t/create-result.json').write_text('{"installationId":"bad"}')
    with pytest.raises(ValueError,match='canonical T'):
        profile._initial('t')


def test_source_records_the_failed_predecessor_order_for_recovery_evidence():
    source=PATH.read_text(encoding='utf-8')
    assert "load('uninstall-s' if action=='prepare' else 'prepare-t')" in source
    assert "profile.lifecycle('t',action)" in source
    assert "current_installation_ref=predecessor" in source
    assert 'S resources released and routes detached before clean T' in source
