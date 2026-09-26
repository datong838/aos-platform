import importlib.util
import json
import sys
from pathlib import Path

import pytest
from aos_api.asset_registry.manifest_loader import ManifestLoader


ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / 'scripts/prepare_ecommerce_growth_1_11_candidate.py'
BASE = ROOT / 'bundles/candidates/ecommerce/solution.ecommerce.growth/1.10.0'
TARGET = BASE.parent / '1.11.0'


def module():
    sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location('growth_1_11_prepare', SCRIPT)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    sys.path.remove(str(SCRIPT.parent))
    return value


def test_content_successor_is_new_unbuilt_source_and_history_unchanged():
    source = module()
    assert source.tree_hash(BASE) == source.BASE_HASH
    assert TARGET.is_dir()
    assert not (TARGET / 'bundle.signature.json').exists()
    assert not (TARGET / 'evidence/bundle-evals.json').exists()
    assert not (TARGET / 'artifacts/runtime-image-index.json').exists()
    assert json.loads((TARGET / 'evidence/content-source-provenance.json').read_text())['status'] == 'UNBUILT_UNSIGNED'
    assert '  version: 1.11.0\n' in (TARGET / 'bundle.yaml').read_text()
    assert (TARGET / 'backend/ecommerce_growth/__init__.py').read_bytes() == (BASE / 'backend/ecommerce_growth/__init__.py').read_bytes()
    for relative in source.SOURCES:
        assert (TARGET / relative).read_bytes() == (source.AUTHOR / relative).read_bytes()
    with pytest.raises(ValueError, match='already exists'):
        source.prepare()


def test_prepare_rejects_drift_before_writing(tmp_path, monkeypatch):
    source = module()
    monkeypatch.setattr(source, 'BASE_HASH', '0' * 64)
    target = tmp_path / '1.11.0'
    with pytest.raises(ValueError, match='baseline drifted'):
        source.prepare(target)
    assert not target.exists()


def test_manifest_and_package_declare_the_same_operations(monkeypatch):
    loaded = ManifestLoader({'candidate': BASE.parent}).load('bundle://candidate/1.11.0')
    declared = [item.model_dump(by_alias=True, mode='json', exclude_none=True)
                for item in loaded.manifest.spec.contributions]
    monkeypatch.syspath_prepend(str(ROOT / 'packages/aos-extension-sdk/python'))
    name = 'ecommerce_growth_candidate_111_test'
    spec = importlib.util.spec_from_file_location(name,
        TARGET / 'backend/ecommerce_growth/__init__.py',
        submodule_search_locations=[str(TARGET / 'backend/ecommerce_growth')])
    package = importlib.util.module_from_spec(spec)
    sys.modules[name] = package
    try:
        spec.loader.exec_module(package)
        assert package.register(object())['contributions'] == declared
        assert len([item for item in declared if item['kind'] == 'api']) == 11
        assert any(item.get('operationId') == 'ecommerce_growth_content_generate'
                   for item in declared)
    finally:
        sys.modules.pop(name, None)
