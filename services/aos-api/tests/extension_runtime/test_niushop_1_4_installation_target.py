import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location('niushop_installation_targets', ROOT / 'scripts/a0v_ecommerce_1_7_first_install.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def test_new_installation_is_distinct_and_version_bound():
    old = M.installation_target()
    config = M.installation_target(after_config_recovery=True)
    sleep = M.installation_target(after_sleep_recovery=True)
    fresh = M.installation_target(niushop_1_4=True)
    assert old == (M.STATE, 'a0v-ecommerce-1.7', '1.3.0', None)
    assert all(item[2] == '1.3.0' for item in [config, sleep])
    assert fresh[0].name == 'niushop-1.4-first-install.json'
    assert fresh[1:] == ('a0v-niushop-1.4', '1.4.0', 'a0fd8e25-cb6f-49e5-aa77-7faddae12099')
    assert len({item[0] for item in [old, config, sleep, fresh]}) == 4
    assert len({item[1] for item in [old, config, sleep, fresh]}) == 4
    with pytest.raises(ValueError):
        M.installation_target(after_sleep_recovery=True, niushop_1_4=True)


@pytest.mark.parametrize('predecessor_active', [False, True])
def test_create_cli_forwards_new_version_and_requires_retired_predecessor(tmp_path, monkeypatch, predecessor_active):
    import sys
    from contextlib import contextmanager
    from types import SimpleNamespace
    @contextmanager
    def connect():
        yield SimpleNamespace(execute=lambda *a: SimpleNamespace(fetchone=lambda: {'n': 0}))
    calls, predecessors = [], []
    def get(**kwargs):
        predecessors.append(kwargs['installation_id'])
        active = predecessor_active and kwargs['installation_id'] == 'a0fd8e25-cb6f-49e5-aa77-7faddae12099'
        return SimpleNamespace(state='active' if active else 'uninstalled', active_revision=5 if active else None)
    def create(**kwargs):
        calls.append(kwargs)
        return {'installationId': 'fixture-only'}
    first = SimpleNamespace(container_database_connect_factory=lambda **kw: connect,
                            create_approved_first_installation=create)
    activation = SimpleNamespace(INSTALLATION_ID='original-invalid',
        _services=lambda *args: (SimpleNamespace(get_installation=get), None))
    monkeypatch.setattr(M, 'RECOVERY', tmp_path)
    monkeypatch.setattr(M, 'load', lambda name: first if name == 'a0v_canonical_ecommerce_first_install' else activation)
    monkeypatch.setattr(sys, 'argv', ['install', '--action', 'create', '--niushop-1-4', '--output', str(tmp_path / 'receipt.json')])
    if predecessor_active:
        with pytest.raises(ValueError, match='formally uninstalled'):
            M.main()
        assert calls == [] and not (tmp_path / 'state/niushop-1.4-first-install.json').exists()
        return
    M.main()
    assert len(calls) == 1 and calls[0]['adapter_version'] == '1.4.0'
    assert calls[0]['core_version'] == '1.3.0' and calls[0]['growth_version'] == '1.7.0'
    assert calls[0]['idempotency_prefix'] == 'a0v-niushop-1.4-first-install-v1'
    assert 'a0fd8e25-cb6f-49e5-aa77-7faddae12099' in predecessors
    assert json.loads((tmp_path / 'state/niushop-1.4-first-install.json').read_text())['installationId'] == 'fixture-only'


def test_reset_is_fixed_to_observed_unbound_installation():
    actual='afd792de-e85e-4680-86d0-c83404824fb3'
    assert M.reset_target(niushop_1_4=True,installation_id=actual)==(actual,'"4"','a0v-niushop-1.4-preparation-reset-r4')
    with pytest.raises(ValueError):M.reset_target(installation_id=actual)
    with pytest.raises(ValueError):M.reset_target(niushop_1_4=True,installation_id='a0fd8e25-cb6f-49e5-aa77-7faddae12099')
