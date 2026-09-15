import importlib
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def profile(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[4] / 'scripts'))
    return importlib.import_module('a0v_ecommerce_bootstrap_reinstall')


def retired(profile):
    return dict(head=dict(installation_id=profile.PREVIOUS_ID, etag_version=5, state='active',
        lock_hash='sha256:'+'a'*64, overlay_revision='test'),
        bindings=[dict(generation=profile.PREVIOUS_GENERATION, enabled=False, operation_fence=True,
            desired_state='disabled', observed_state='unknown')],
        resources=[dict(cleanup_state='released', observed_release=True)],
        operations=[dict(status='succeeded')], canaryInstallations=0)


def test_profile_preserves_historical_coordinates(profile):
    old = importlib.import_module('a0v_ecommerce_current_reinstall')
    configured = profile.load_profile()
    assert old.VERSIONS['solution.ecommerce.growth'] == '1.8.0'
    assert configured.VERSIONS['solution.ecommerce.growth'] == '1.10.0'
    assert configured.STATE == profile.STATE and configured.STATE != old.STATE
    assert configured.BUNDLE_ROOT == profile.BUNDLE_ROOT
    with pytest.raises(ValueError):
        profile.initial('a')


@pytest.mark.parametrize('fault', ['id', 'generation', 'enabled', 'resource', 'operation', 'canary'])
def test_fixed_released_predecessor_required(profile, fault):
    base = profile.load_profile()
    original = retired(profile)
    assert profile.require_retired_h(base, original)['installationId'] == profile.PREVIOUS_ID
    value = deepcopy(original)
    if fault == 'id': value['head']['installation_id'] = 'wrong'
    if fault == 'generation': value['bindings'][0]['generation'] = 'wrong'
    if fault == 'enabled': value['bindings'][0]['enabled'] = True
    if fault == 'resource': value['resources'][0]['observed_release'] = False
    if fault == 'operation': value['operations'][0]['status'] = 'running'
    if fault == 'canary': value['canaryInstallations'] = 1
    with pytest.raises(ValueError):
        profile.require_retired_h(base, value)


@pytest.mark.parametrize(('rows', 'attached', 'allowed'), [
    ([{'status':'detached'}], 0, True), ([], 0, False),
    ([{'status':'fenced'}], 0, False), ([{'status':'detached'}], 1, False),
    ([{'status':'detached'}, {'status':'detached'}], 0, False)])
def test_detach_must_be_unique_and_all_dispatches_removed(profile, rows, attached, allowed):
    class Connection:
        def execute(self, query, params):
            assert params[0] == profile.PREVIOUS_ID
            return SimpleNamespace(fetchall=lambda: rows, fetchone=lambda: {'n': attached})
    @contextmanager
    def connect():
        yield Connection()
    if allowed:
        assert profile.require_detached_h(connect) is None
    else:
        with pytest.raises(ValueError, match='disable/detach'):
            profile.require_detached_h(connect)


@pytest.mark.parametrize('action', ['prepare-i', 'verify-i', 'stage-i', 'configure-i', 'enable-i'])
def test_f_stages_use_only_fixed_f(profile, monkeypatch, action):
    monkeypatch.setattr(profile, 'initial', lambda label: {'installationId': profile.PREVIOUS_ID})
    called = []
    base = SimpleNamespace(lifecycle=lambda *args: called.append(('lifecycle', args)),
                           configure=lambda *args: called.append(('configure', args)))
    profile.run(action, base)
    phase = action.split('-')[0]
    assert called == [('lifecycle' if phase in {'prepare','verify'} else 'configure', ('i', phase))]
    with pytest.raises(ValueError):
        profile.run('disable-other', base)


def test_disable_refuses_recovered_predecessor_generation(profile, monkeypatch):
    monkeypatch.setattr(profile, 'initial', lambda label: {'installationId': profile.PREVIOUS_ID})
    value = retired(profile)
    value['bindings'][0]['generation'] = 'another-generation'
    called = []
    base = SimpleNamespace(observe_installation=lambda _: value,
                           disable=lambda *args, **kwargs: called.append(args))
    with pytest.raises(ValueError, match='generation'):
        profile.run('disable-h', base)
    assert called == []


@pytest.mark.parametrize('rows,allowed', [([],False), ([{'attached':8}],False),
    ([{'attached':9},{'attached':9}],False), ([{'attached':9,'cutover_operation_id':'activation'}],True)])
def test_recovery_requires_one_orphaned_nine_entry_group(profile,rows,allowed):
    class Connection:
        def execute(self,query,params):
            assert params==(profile.PREVIOUS_ID,profile.PREVIOUS_GENERATION)
            return SimpleNamespace(fetchall=lambda:rows)
    @contextmanager
    def connect():
        yield Connection()
    if allowed:
        assert profile.require_orphaned_h(connect)=='activation'
    else:
        with pytest.raises(ValueError,match='orphaned'):
            profile.require_orphaned_h(connect)


def test_reconcile_rejects_unreleased_generation_before_request(profile,monkeypatch):
    snapshot=retired(profile)
    snapshot['resources'][0]['observed_release']=False
    base=profile.load_profile()
    monkeypatch.setattr(base,'observe_installation',lambda _:snapshot)
    monkeypatch.setattr(base,'_setup_runtime_plane',lambda:pytest.fail('invalid predecessor reached write service'))
    with pytest.raises(ValueError,match='released resources'):
        profile.reconcile_h(base)
