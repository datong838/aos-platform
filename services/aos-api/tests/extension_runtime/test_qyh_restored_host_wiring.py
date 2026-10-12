"""Routing and fail-closed checks only; fixtures grant no runtime authority."""
import json
from types import SimpleNamespace

import pytest

from aos_api.asset_registry import control_wiring as wiring


@pytest.fixture
def restored(monkeypatch, tmp_path):
    for name in ('AOS_CURRENT_SIGNED_RECEIPT', 'AOS_CURRENT_RESTORED_API_IDENTITY_FILE',
                 'AOS_CURRENT_RESTORED_INSTALLATION_ID'):
        monkeypatch.delenv(name, raising=False)
    root = tmp_path / 'bundles'
    root.mkdir()
    trust = tmp_path / 'roots.json'
    trust.write_text('{}')
    monkeypatch.setenv('AOS_BUNDLE_ROOT', str(root))
    monkeypatch.setenv('AOS_BUNDLE_TRUST_ROOTS_FILE', str(trust))
    monkeypatch.setenv('AOS_CURRENT_RESTORED_API_IDENTITY_FILE', '/protected/restored.json')
    monkeypatch.setenv('AOS_CURRENT_RESTORED_INSTALLATION_ID', 'ab2fd72f-d81c-400d-bbbc-e1589a159d6b')
    return root, trust


def call_gate(**changes):
    return wiring._current_a0v_host_preflight(**{
        'signed_receipt': '', 'credential_reference': '/protected/planes.json',
        'preparation_only': True, **changes})


def test_explicit_restored_route_dispatches_exact_original_cli(monkeypatch, restored):
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=2, stdout='')
    monkeypatch.setattr(wiring.subprocess, 'run', run)
    assert call_gate() is False  # Failed preflight is never admitted.
    assert len(calls) == 1
    command, kwargs = calls[0]
    assert command[2:] == ['--credential-file', '/protected/planes.json',
        '--restored-api-identity', '/protected/restored.json',
        '--restored-installation', 'ab2fd72f-d81c-400d-bbbc-e1589a159d6b',
        '--bundle-root', str(restored[0]), '--trust-roots-file', str(restored[1]),
        '--preparation-only']
    assert kwargs['env']['AOS_DOTENV_DISABLED'] == '1'


@pytest.mark.parametrize('invalid', ['full', 'mixed', 'missing-identity', 'empty-installation',
                                     'relative-identity', 'relative-root'])
def test_invalid_explicit_restored_route_has_no_subprocess_or_legacy_fallback(monkeypatch, restored, invalid):
    kwargs = {}
    if invalid == 'full': kwargs['preparation_only'] = False
    if invalid == 'mixed': kwargs['signed_receipt'] = '/signed/historical.json'
    if invalid == 'missing-identity': monkeypatch.delenv('AOS_CURRENT_RESTORED_API_IDENTITY_FILE')
    if invalid == 'empty-installation': monkeypatch.setenv('AOS_CURRENT_RESTORED_INSTALLATION_ID', '')
    if invalid == 'relative-identity': monkeypatch.setenv('AOS_CURRENT_RESTORED_API_IDENTITY_FILE', 'relative.json')
    if invalid == 'relative-root': monkeypatch.setenv('AOS_BUNDLE_ROOT', 'relative')
    monkeypatch.setattr(wiring.subprocess, 'run', lambda *_a, **_k: pytest.fail('preflight dispatched'))
    assert call_gate(**kwargs) is False


def test_original_builder_reaches_restored_preflight_without_historical_receipt(monkeypatch, restored):
    monkeypatch.setenv('AOS_EXTENSION_RUNTIME_HOST_ENABLED', '1')
    monkeypatch.setenv('AOS_EXTENSION_RUNTIME_PREPARATION_ONLY', '1')
    monkeypatch.setenv('AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE', '/protected/planes.json')
    calls = []
    def rejected(**kwargs):
        calls.append(kwargs)
        return False
    monkeypatch.setattr(wiring, '_current_a0v_host_preflight', rejected)
    selection = wiring.build_production_runtime_host_selection(control_plane=None)
    assert selection.status == 'INACTIVE'
    assert selection.error_code == 'CURRENT_SIGNED_HOST_PREFLIGHT_FAILED'
    assert calls == [{'signed_receipt': '', 'credential_reference': '/protected/planes.json',
                      'preparation_only': True}]


@pytest.mark.parametrize('changed', ['installation', 'database', 'mode', 'authorization'])
def test_restored_report_must_match_requested_installation_and_current_database(monkeypatch, restored, changed):
    report = {'outcome': 'CURRENT_SIGNED_HOST_READONLY_PREFLIGHT_GREEN',
        'authorization': 'PREFLIGHT_ONLY_NO_RUNTIME_START', 'scope': ['org-org', 'dev-project'],
        'admissionMode': 'PREPARATION_ONLY', 'database': 'aos_meta_head',
        'installationId': 'ab2fd72f-d81c-400d-bbbc-e1589a159d6b',
        'databaseAuthority': ['172.0.0.2', 5432, 'aos_meta_head'],
        'signedRoot': str(restored[0]), 'trustRoots': str(restored[1])}
    if changed == 'installation': report['installationId'] = 'old'
    if changed == 'database': report['database'] = 'old'
    if changed == 'mode': report['admissionMode'] = 'FULL'
    if changed == 'authorization': report['authorization'] = 'START'
    monkeypatch.setattr(wiring.subprocess, 'run', lambda *_a, **_k:
                        SimpleNamespace(returncode=0, stdout=json.dumps(report)))
    import psycopg
    monkeypatch.setattr(psycopg, 'connect', lambda *_a, **_k: pytest.fail('untrusted report connected'))
    assert call_gate() is False


def test_restored_success_keeps_original_api_authority_and_generation_pins(monkeypatch, restored):
    report = {'outcome': 'CURRENT_SIGNED_HOST_READONLY_PREFLIGHT_GREEN',
        'authorization': 'PREFLIGHT_ONLY_NO_RUNTIME_START', 'scope': ['org-org', 'dev-project'],
        'admissionMode': 'PREPARATION_ONLY', 'database': 'aos_meta_head',
        'installationId': 'ab2fd72f-d81c-400d-bbbc-e1589a159d6b',
        'databaseAuthority': ['172.0.0.2', 5432, 'aos_meta_head'],
        'signedRoot': str(restored[0]), 'trustRoots': str(restored[1]),
        'credentialFileGeneration': [1, 2, 3, 4, 5]}
    monkeypatch.setattr(wiring.subprocess, 'run', lambda *_a, **_k:
                        SimpleNamespace(returncode=0, stdout=json.dumps(report)))
    monkeypatch.setattr('aos_api.db.get_dsn', lambda: 'fixture-api-dsn')
    pins, roots = [], []
    monkeypatch.setattr('aos_api.extension_runtime.runtime_connections.pin_runtime_file_generation',
                        lambda path, generation: pins.append((path, generation)))
    monkeypatch.setattr('aos_api.aip_responsibility_template_authority.pin_verified_signed_release_root',
                        lambda root: roots.append(root))
    class Conn:
        read_only = False
        database = 'aos_meta_head'
        def __enter__(self): return self
        def __exit__(self, *_): return None
        def execute(self, query):
            assert self.read_only is True
            assert 'SELECT' in query
            return self
        def fetchone(self):
            return {'server_addr': '172.0.0.2', 'server_port': 5432, 'database_name': self.database}
    conn = Conn()
    monkeypatch.setattr('psycopg.connect', lambda *_a, **_k: conn)
    assert call_gate() is True
    assert pins == [('/protected/planes.json', [1, 2, 3, 4, 5])]
    assert roots == [restored[0]]
    conn.database = 'another_database'
    assert call_gate() is False
    assert len(pins) == len(roots) == 1
    conn.database = 'aos_meta_head'
    report['databaseAuthority'][2] = 'another_database'
    assert call_gate() is False
    report['databaseAuthority'][2] = 'aos_meta_head'
    monkeypatch.setattr('aos_api.extension_runtime.runtime_connections.pin_runtime_file_generation',
                        lambda *_: (_ for _ in ()).throw(RuntimeError('file changed')))
    assert call_gate() is False
    assert len(roots) == 1
