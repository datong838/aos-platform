import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def successor():
    return load(ROOT / 'scripts/a0v_niushop_1_4_registry_successor.py', 'niushop_registry_profile').load_successor()


def test_profile_is_private_and_old_defaults_unchanged():
    current = successor()
    old = load(ROOT / 'scripts/a0v_ecommerce_1_7_registry_successor.py', 'original_registry_profile')
    assert current.VERSIONS['platform.ecommerce.niushop'] == '1.4.0'
    assert old.VERSIONS['platform.ecommerce.niushop'] == '1.3.0'
    assert (current.EXPECTED_OLD_COUNT, current.EXPECTED_NEW_COUNT) == (11, 12)
    assert (old.EXPECTED_OLD_COUNT, old.EXPECTED_NEW_COUNT) == (8, 11)
    assert current.OLD_ROOT == old.NEW_ROOT
    assert current.ENV_BACKUP_NAME != old.ENV_BACKUP_NAME
    assert current.legacy()._builder().RUNTIME_CASES[1][2] == '1.4.0'


@pytest.fixture
def fixture_build(tmp_path, monkeypatch):
    module = successor()
    helper = module.legacy()
    builder = helper._builder()
    fixtures = load(ROOT / 'services/aos-api/tests/extension_runtime/test_a0v_ecommerce_growth_1_5_registry_successor.py', 'niushop_registry_fixture_helpers')
    monkeypatch.setattr(fixtures.SUCCESSOR, '_builder', lambda: builder)
    coordinates = tuple(case[:3] for case in builder.ALL_CASES)
    monkeypatch.setattr(fixtures.SUCCESSOR, 'CURRENT_COORDINATES', coordinates)
    monkeypatch.setattr(fixtures.SUCCESSOR, 'HISTORICAL_COORDINATES', tuple(case for case in coordinates if case[1] != 'platform.ecommerce.niushop'))
    output, receipt, qualification = fixtures._build_fixture(tmp_path)
    document = json.loads(qualification.read_text())
    document['runtimeSessions'] = {key: {'registration': 'exact', 'heartbeat': 'alive', 'cleanup': 'released',
        'contributionCount': count, 'heartbeatChecks': 2048} for key, count in [
        ('domain.ecommerce.core', 1), ('platform.ecommerce.niushop', 2), ('solution.ecommerce.growth', 23)]}
    qualification.write_text(json.dumps(document))
    state = fixtures._first_state(tmp_path, output)
    monkeypatch.setattr(module, 'BUILD', output)
    monkeypatch.setattr(module, 'BUILD_RECEIPT', receipt)
    monkeypatch.setattr(module, 'QUALIFICATION', qualification)
    monkeypatch.setattr(module, 'OLD_ROOT', state / 'signed-bundles-v4')
    monkeypatch.setattr(module, 'STATE', tmp_path / 'successor')
    monkeypatch.setattr(module, 'NEW_ROOT', module.STATE / 'signed-bundles-next')
    monkeypatch.setattr(module, 'EXPECTED_OLD_COUNT', 3)
    monkeypatch.setattr(module, 'EXPECTED_NEW_COUNT', 4)
    monkeypatch.setattr(helper, 'FIRST_INSTALL_STATE', state)
    monkeypatch.setattr(helper, '_git', lambda *args: '')
    return module, helper, builder


def test_signed_successor_preserves_history_and_replays(fixture_build):
    module, helper, builder = fixture_build
    build = module.verify_inputs(helper)
    before = builder._tree_hash(module.OLD_ROOT)
    first = module.signed_tree(helper, build)
    assert len(first[1]) == 4
    assert module.signed_tree(helper, build) == first
    assert builder._tree_hash(module.OLD_ROOT) == before
    for key, version in module.VERSIONS.items():
        assert first[1][key + '/' + version] == build['contentHashes'][key]


def test_historical_content_cannot_be_replaced(fixture_build):
    module, helper, _ = fixture_build
    build = module.verify_inputs(helper)
    build['contentHashes']['domain.ecommerce.core'] = 'sha256:' + '0' * 64
    with pytest.raises(ValueError, match='historical content changed'):
        module.signed_tree(helper, build)
    assert not module.NEW_ROOT.exists()


def test_bad_qualification_or_dirty_sources_rejected(fixture_build, monkeypatch):
    module, helper, _ = fixture_build
    document = json.loads(module.QUALIFICATION.read_text())
    document['runtimeSessions']['platform.ecommerce.niushop']['cleanup'] = 'unknown'
    module.QUALIFICATION.write_text(json.dumps(document))
    with pytest.raises(ValueError, match='incomplete'):
        module.verify_inputs(helper)
    document['runtimeSessions']['platform.ecommerce.niushop']['cleanup'] = 'released'
    module.QUALIFICATION.write_text(json.dumps(document))
    monkeypatch.setattr(helper, '_git', lambda *args: 'dirty' if args[0] == 'diff' else '')
    with pytest.raises(ValueError, match='advanced or dirty'):
        module.verify_inputs(helper)


def test_new_root_switch_uses_separate_backup_and_cas(tmp_path, monkeypatch):
    module = successor()
    monkeypatch.setattr(module, 'STATE', tmp_path)
    path = tmp_path / 'env'
    original = f'AOS_BUNDLE_ROOT={module.OLD_ROOT}\nUNCHANGED=value\n'
    path.write_text(original)
    assert module.switch_root(path) is True
    assert module.switch_root(path) is False
    assert (tmp_path / module.ENV_BACKUP_NAME).read_text() == original
    path.write_text('AOS_BUNDLE_ROOT=/unexpected\n')
    with pytest.raises(ValueError, match='CAS'):
        module.switch_root(path)
