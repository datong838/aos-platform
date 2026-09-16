"""Pure gates for the fixed J uninstall/K replacement executor."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'scripts'))


@pytest.fixture
def recovery():
    path = Path(__file__).resolve().parents[4] / 'scripts/a0v_j_uninstall_reinstall_recovery.py'
    spec = importlib.util.spec_from_file_location('a0v_j_uninstall_reinstall_recovery_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def j_snapshot(recovery):
    return {
        'head': {'installation_id': recovery.J_ID, 'etag_version': 5, 'state': 'active',
                 'lock_hash': recovery.J_LOCK,
                 'overlay_revision': 'a0v-canonical-ecommerce-v1'},
        'bindings': [{'generation': recovery.J_GENERATION, 'revision': 11,
                      'execution_epoch': 6, 'enabled': False, 'operation_fence': True,
                      'desired_state': 'disabled', 'observed_state': 'unknown'}],
        'operations': [{'status': 'succeeded'}],
        'resources': [{'cleanup_state': 'released', 'observed_release': True}
                      for _ in range(3)],
        'canaryInstallations': 0,
    }


def k_snapshot(recovery, status='failed', *, reset=False):
    return {
        'head': {'installation_id': '6dcae78b-a1e9-402c-ad09-36b111f52698',
                 'etag_version': 4 if reset else 5,
                 'state': 'applied' if reset else 'approved', 'lock_hash': 'lock-k'},
        'bindings': [],
        'operations': [{'operation_id': '10000000-0000-0000-0000-000000000001',
                        'kind': 'runtime-apply', 'status': 'succeeded',
                        'phase': 'succeeded', 'deadline_expired': True},
                       {'operation_id': '10000000-0000-0000-0000-000000000002',
                        'kind': 'runtime-verify', 'status': status,
                        'phase': 'accepted' if status == 'accepted' else status,
                        'deadline_expired': True}],
        'resources': [{'cleanup_state': 'released', 'observed_release': True}
                      for _ in range(3)],
        'canaryInstallations': 0,
    }


@pytest.mark.parametrize('fault', ('binding', 'resource', 'operation', 'canary'))
def test_require_j_is_fail_closed(recovery, fault):
    value = j_snapshot(recovery)
    if fault == 'binding':
        value['bindings'][0]['operation_fence'] = False
    elif fault == 'resource':
        value['resources'][0]['observed_release'] = False
    elif fault == 'operation':
        value['operations'][0]['status'] = 'running'
    else:
        value['canaryInstallations'] = 1
    with pytest.raises(ValueError, match='exact disabled released J'):
        recovery.require_j(SimpleNamespace(observe_installation=lambda _identity: value))


def test_require_j_accepts_only_the_fixed_identity(recovery):
    value = j_snapshot(recovery)
    assert recovery.require_j(
        SimpleNamespace(observe_installation=lambda identity: value)
    ) is value


def test_k_lifecycle_waits_for_formal_j_uninstall(recovery, monkeypatch):
    current = SimpleNamespace(
        observe_installation=lambda _identity: {'head': {'state': 'active'}},
        lifecycle=lambda *_args: pytest.fail('lifecycle must not start'),
    )
    monkeypatch.setattr(recovery, 'profile', lambda: current)
    with pytest.raises(ValueError, match='formally uninstalled'):
        recovery.run('prepare-k')


def test_uninstall_waits_for_approved_unprepared_k(recovery, monkeypatch):
    j = j_snapshot(recovery)
    current = SimpleNamespace(
        observe_installation=lambda identity: j if identity == recovery.J_ID else {
            'head': {'state': 'active', 'etag_version': 5}, 'bindings': [{}]},
        _initial=lambda _label: {'installationId': 'e7bcc9a6-1ec8-4578-b6ad-a4ef0e5375be'},
    )
    monkeypatch.setattr(recovery, 'require_j', lambda _current: deepcopy(j))
    with pytest.raises(ValueError, match='approved unprepared K'):
        recovery.uninstall_j(current)


def test_interrupted_k_must_have_terminal_verify(recovery):
    value = k_snapshot(recovery, status='accepted')
    current = SimpleNamespace(
        _initial=lambda _label: {'installationId': value['head']['installation_id'],
                                 'lockHash': 'lock-k'},
        observe_installation=lambda _identity: value,
    )
    with pytest.raises(ValueError, match='resettable or terminal released K'):
        recovery.require_interrupted_k(current)


def test_interrupted_k_accepts_failed_verify_after_release(recovery):
    value = k_snapshot(recovery)
    current = SimpleNamespace(
        _initial=lambda _label: {'installationId': value['head']['installation_id'],
                                 'lockHash': 'lock-k'},
        observe_installation=lambda _identity: value,
    )
    assert recovery.require_interrupted_k(current) is value


def test_interrupted_k_reset_requires_expired_accepted_verify(recovery):
    value = k_snapshot(recovery, status='accepted', reset=True)
    current = SimpleNamespace(
        _initial=lambda _label: {'installationId': value['head']['installation_id'],
                                 'lockHash': 'lock-k'},
        observe_installation=lambda _identity: value,
    )
    assert recovery.require_interrupted_k(current, reset=True) is value
    value['operations'][1]['deadline_expired'] = False
    with pytest.raises(ValueError, match='resettable or terminal released K'):
        recovery.require_interrupted_k(current, reset=True)


def test_l_lifecycle_waits_for_formal_k_uninstall(recovery, monkeypatch):
    current = SimpleNamespace(
        _initial=lambda _label: {'installationId': '6dcae78b-a1e9-402c-ad09-36b111f52698'},
        observe_installation=lambda _identity: {'head': {'state': 'applied'}},
        lifecycle=lambda *_args: pytest.fail('lifecycle must not start'),
    )
    monkeypatch.setattr(recovery, 'profile', lambda: current)
    with pytest.raises(ValueError, match='K must be formally uninstalled'):
        recovery.run('prepare-l')


def test_l_lifecycle_targets_l_after_k_uninstall(recovery, monkeypatch):
    calls = []
    current = SimpleNamespace(
        _initial=lambda _label: {'installationId': '6dcae78b-a1e9-402c-ad09-36b111f52698'},
        observe_installation=lambda _identity: {'head': {'state': 'uninstalled'}},
        lifecycle=lambda label, phase: calls.append((label, phase)) or {'ok': True},
    )
    monkeypatch.setattr(recovery, 'profile', lambda: current)
    assert recovery.run('prepare-l') == {'ok': True}
    assert calls == [('l', 'prepare')]
