import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def deploy(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[4] / 'scripts'))
    return importlib.import_module('a0v_event_dispatch_deploy')


def test_exact_deployment_scope(deploy):
    assert (deploy.SOURCE, deploy.TARGET, deploy.CHAIN) == ('a0v_053', 'a0v_054', ['a0v_054'])
    assert deploy.CLONE == 'aos_event_dispatch_quiesced_20260916_test'
    assert deploy.storage.MAIN == 'aos_meta_head'
    assert deploy.FILES == ('a0v_054_event_control_dispatch_lifecycle.py',)


def test_output_is_private_and_never_overwritten(deploy, tmp_path):
    path = tmp_path / 'proof.json'
    deploy.protected_write(path, {'first': True})
    with pytest.raises(FileExistsError):
        deploy.protected_write(path, {'first': False})
    assert json.loads(path.read_text()) == {'first': True}
    assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('bad', [{}, {'outcome': 'EVENT_DISPATCH_RESTORE_VERIFIED', 'source': 'a0v_052'},
                                 {'outcome': 'EVENT_DISPATCH_RESTORE_VERIFIED', 'source': 'a0v_053', 'target': 'a0v_055'}])
def test_wrong_preparation_never_reaches_database(deploy, bad):
    with pytest.raises(ValueError, match='preparation proof differs'):
        deploy.validate_proof(bad)


def test_existing_apply_intent_rejects_before_database(deploy, monkeypatch, tmp_path):
    monkeypatch.setattr(deploy, 'STATE', tmp_path)
    monkeypatch.setattr(deploy, 'require_lease', lambda: None)
    (tmp_path / 'apply-intent.json').write_text('{}')
    with pytest.raises(ValueError, match='existing intent'):
        deploy.apply()
