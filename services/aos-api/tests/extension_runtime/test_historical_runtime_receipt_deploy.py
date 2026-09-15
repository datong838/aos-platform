import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def deploy(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[4] / 'scripts'))
    return importlib.import_module('a0v_historical_runtime_receipt_deploy')


def test_exact_deployment_scope(deploy):
    assert (deploy.SOURCE, deploy.TARGET, deploy.CHAIN) == ('a0v_058', 'a0v_059', ['a0v_059'])
    assert deploy.CLONE == 'aos_historical_runtime_receipt_20260916_test'
    assert deploy.storage.MAIN == 'aos_meta_head'
    assert deploy.FILES == ('a0v_059_historical_runtime_receipt.py',)


def test_output_is_private_and_never_overwritten(deploy, tmp_path):
    path = tmp_path / 'proof.json'
    deploy.protected_write(path, {'first': True})
    with pytest.raises(FileExistsError):
        deploy.protected_write(path, {'first': False})
    assert json.loads(path.read_text()) == {'first': True}
    assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('bad', [{}, {'outcome': 'HISTORICAL_RUNTIME_RECEIPT_RESTORE_VERIFIED', 'source': 'a0v_052'},
                                 {'outcome': 'HISTORICAL_RUNTIME_RECEIPT_RESTORE_VERIFIED', 'source': 'a0v_053', 'target': 'a0v_055'}])
def test_wrong_preparation_never_reaches_database(deploy, bad):
    with pytest.raises(ValueError, match='preparation proof differs'):
        deploy.validate_proof(bad)


def test_existing_apply_intent_rejects_before_database(deploy, monkeypatch, tmp_path):
    monkeypatch.setattr(deploy, 'STATE', tmp_path)
    monkeypatch.setattr(deploy, 'require_lease', lambda: None)
    (tmp_path / 'apply-intent.json').write_text('{}')
    with pytest.raises(ValueError, match='existing intent'):
        deploy.apply()


@pytest.mark.parametrize('returncode', [0, 1])
def test_backup_and_fingerprint_share_live_snapshot(deploy, monkeypatch, tmp_path, returncode):
    from contextlib import contextmanager
    from types import SimpleNamespace
    events = []
    class Connection:
        info = SimpleNamespace(user='test_owner')
        def execute(self, query, args=None):
            events.append(query)
            if query.startswith('SELECT 1'):return SimpleNamespace(fetchone=lambda: None)
            if 'pg_export_snapshot' in query:
                return SimpleNamespace(fetchone=lambda: {'snapshot': '000001-000002-1'})
    @contextmanager
    def connect(database):
        events.append('opened')
        try:yield Connection()
        finally:events.append('closed')
    def dump(args, **kwargs):
        assert 'closed' not in events
        assert args[-2:] == ['--snapshot', '000001-000002-1']
        assert events.index('fingerprint') > events.index('SELECT pg_export_snapshot() AS snapshot')
        kwargs['stdout'].write(b'custom-format-backup')
        events.append('dump')
        return SimpleNamespace(returncode=returncode)
    monkeypatch.setattr(deploy.storage, 'connect', connect)
    monkeypatch.setattr(deploy.storage, 'version', lambda conn: [deploy.SOURCE])
    monkeypatch.setattr(deploy.storage, 'fingerprint', lambda conn: events.append('fingerprint') or {'existing': 1})
    monkeypatch.setattr(deploy.subprocess, 'run', dump)
    path = tmp_path / 'backup.dump'
    if returncode:
        with pytest.raises(RuntimeError, match='backup failed'):deploy.snapshot_backup(path)
    else:
        assert deploy.snapshot_backup(path) == ({'existing': 1}, 'test_owner', '000001-000002-1')
    assert events[1] == 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'
    assert events[-2:] == ['dump', 'closed']
    assert path.read_bytes() == b'custom-format-backup'
    assert path.stat().st_mode & 0o777 == 0o600
