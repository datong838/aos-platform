"""Configuration-only candidate fixtures; not current installation acceptance."""
import importlib.util
from pathlib import Path
import pytest
from aos_api.asset_registry.composition_contracts import ResolvedBundle
from aos_api.extension_runtime.runtime_release_artifacts import CurrentRuntimeReleaseArtifacts

ROOT = Path(__file__).resolve().parents[3]


def load():
    spec = importlib.util.spec_from_file_location('snapshot_preview', ROOT / 'scripts/a0v_snapshot_configuration_preview.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def artifacts():
    reader = object.__new__(CurrentRuntimeReleaseArtifacts)
    root = ROOT / 'bundles/candidates/ecommerce/platform.ecommerce.niushop/1.23.0'
    reader.read_artifact = lambda selected, path, limit: (root / path).read_bytes()
    # Named fixture seam: no Registry, signature or installation claim.
    selected = ResolvedBundle.model_construct(id='platform.ecommerce.niushop', version='1.23.0',
        publisher='aos', content_hash='sha256:' + 'a' * 64)
    return reader, selected


def test_complete_deterministic_preview_never_enables_schedule(artifacts):
    reader, selected = artifacts
    module = load()
    a = module.build_preview(reader, selected, 'niushop-qyh')
    assert a == module.build_preview(reader, selected, 'niushop-qyh')
    assert a['executionAuthorized'] is False and len(a['members']) == 12
    assert len({m['table'] for m in a['members']}) == 12
    assert all(m['schedule']['enabled'] is False for m in a['members'])
    assert a['members'][1]['graph']['pipeline_id'] == 'P02-product-qyh'
    a['members'][0]['graph']['nodes'][0]['config']['table'] = 'mutated'
    assert module.build_preview(reader, selected, 'niushop-qyh')['members'][0]['table'] == 'ns_site'


def test_wrong_canonical_mapping_fails(artifacts):
    reader, selected = artifacts
    original = reader.read_artifact
    reader.read_artifact = lambda selected, path, limit: original(selected,
        path.replace('p02-product.yaml', 'p01-shop.yaml'), limit)
    with pytest.raises(ValueError, match='canonical'):
        load().build_preview(reader, selected, 'niushop-qyh')


def test_missing_artifact_aborts_whole_preview(artifacts):
    reader, selected = artifacts
    original = reader.read_artifact
    def read(selected, path, limit):
        if 'p12-payment' in path:
            raise ValueError('artifact unavailable')
        return original(selected, path, limit)
    reader.read_artifact = read
    with pytest.raises(ValueError, match='artifact unavailable'):
        load().build_preview(reader, selected, 'niushop-qyh')


@pytest.mark.parametrize('source', ['', ' niushop-qyh', None])
def test_invalid_source_fails_before_artifact_read(artifacts, source):
    reader, selected = artifacts
    reader.read_artifact = lambda *args: pytest.fail('must not read')
    with pytest.raises(ValueError):
        load().build_preview(reader, selected, source)


def test_wrong_dependency_type_rejected(artifacts):
    with pytest.raises(TypeError):
        load().build_preview(object(), artifacts[1], 'niushop-qyh')


def test_duplicate_table_rejected(artifacts, monkeypatch):
    from dataclasses import replace
    module = load()
    original = module.derive_mapping_read_spec
    count = 0
    def derive(*args):
        nonlocal count
        result = original(*args)
        count += 1
        return replace(result, table='ns_site') if count == 2 else result
    monkeypatch.setattr(module, 'derive_mapping_read_spec', derive)
    monkeypatch.setattr(module, 'compile_snapshot_mapping', lambda *args: None)
    with pytest.raises(ValueError, match='unique table'):
        module.build_preview(*artifacts, 'niushop-qyh')


def test_other_package_fails_before_read(artifacts):
    reader, selected = artifacts
    reader.read_artifact = lambda *args: pytest.fail('must not read')
    with pytest.raises(ValueError, match='Niushop'):
        load().build_preview(reader, selected.model_copy(update={'id': 'other.package'}), 'niushop-qyh')
