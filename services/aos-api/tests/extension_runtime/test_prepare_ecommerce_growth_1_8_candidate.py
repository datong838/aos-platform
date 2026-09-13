import importlib
import importlib.util
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import pytest

from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.extension_runtime.ui_resources import FrontendUiManifest
from test_analyst_workspace_view import snapshot
from test_analyst_workspace_runtime import _frame, _responses


@pytest.fixture
def prepare(monkeypatch):
    root = Path(__file__).resolve().parents[4]
    monkeypatch.syspath_prepend(str(root / 'scripts'))
    return importlib.import_module('prepare_ecommerce_growth_1_8_candidate')


def test_cannot_overwrite_or_ignore_baseline_drift(prepare, tmp_path, monkeypatch):
    with pytest.raises(ValueError, match='must not exist'):
        prepare.prepare(tmp_path)
    monkeypatch.setattr(prepare, 'BASE_HASH', 'wrong')
    with pytest.raises(ValueError, match='baseline drifted'):
        prepare.prepare(tmp_path / 'candidate')
    assert not (tmp_path / 'candidate').exists()


def test_source_drift_refused_before_copy(prepare, tmp_path, monkeypatch):
    monkeypatch.setattr(prepare, 'SOURCES', {**prepare.SOURCES, 'frontend/index.html': 'wrong'})
    with pytest.raises(ValueError, match='source drifted'):
        prepare.prepare(tmp_path / 'candidate')
    assert not (tmp_path / 'candidate').exists()


def test_candidate_exact_diff_and_manifest_registration(prepare, tmp_path):
    target = tmp_path / 'candidate'
    receipt = prepare.prepare(target)
    before = {str(p.relative_to(prepare.BASE)):p.read_bytes() for p in prepare.BASE.rglob('*')
              if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    after = {str(p.relative_to(target)):p.read_bytes() for p in target.rglob('*') if p.is_file()}
    assert not set(before) - set(after)
    changed = {p for p in before if before[p] != after[p]}
    assert changed == {'bundle.yaml','backend/ecommerce_growth/__init__.py',*receipt['updatedSelfReferences']}
    assert set(after) - set(before) == {'frontend/index.html','frontend/manifest.json','backend/ecommerce_growth/analyst_workspace_view.py'}
    assert len(receipt['updatedSelfReferences']) == 8
    assert prepare.tree_hash(prepare.BASE) == prepare.BASE_HASH
    loaded = ManifestLoader({'candidate':tmp_path}).load('bundle://candidate/candidate')
    assert loaded.manifest.metadata.version == '1.8.0'
    assert loaded.manifest.spec.permissions.data_scopes == ['ecommerce.workshop.read']
    ui = FrontendUiManifest.model_validate_json(after['frontend/manifest.json'])
    assert ui.routeClaims == ['/workshop/analyst'] and ui.commandOperationClaims == []
    assert ui.readOperationClaims == ['analyst_workspace_view_v1']
    assert loaded.manifest.spec.runtime.frontend.artifact_hash == 'sha256:' + sha256(after['frontend/manifest.json']).hexdigest()
    assert len([x for x in loaded.manifest.spec.contributions if x.kind == 'navigation']) == 7
    expected = [item.model_dump(by_alias=True,mode='json',exclude_none=True) for item in loaded.manifest.spec.contributions]
    # Registration executes only the inert entrypoint; no application or I/O ports.
    module = {'__name__':'candidate_entry'}
    exec(compile(after['backend/ecommerce_growth/__init__.py'], 'candidate_entry', 'exec'), module)
    assert module['register'](object())['contributions'] == expected
    assert len(expected) == 24
    assert receipt['treeHash'] == 'sha256:' + prepare.tree_hash(target)


def test_candidate_sdk_can_project_real_contract_without_host_modules(prepare, tmp_path, monkeypatch):
    target = tmp_path / 'candidate'
    prepare.prepare(target)
    monkeypatch.syspath_prepend(str(prepare.ROOT / 'packages/aos-extension-sdk/python'))
    name = 'ecommerce_growth_candidate_18_test'
    spec = importlib.util.spec_from_file_location(name, target / 'backend/ecommerce_growth/__init__.py',
        submodule_search_locations=[str(target / 'backend/ecommerce_growth')])
    module = importlib.util.module_from_spec(spec)
    import sys
    try:
        sys.modules[name] = module
        spec.loader.exec_module(module)
        serve = importlib.import_module('aos_extension_sdk.session').serve_session
        wire = BytesIO(_frame('register', 'register', {}, 0) +
                       _frame('invoke', 'analyst_workspace_view_v1', {'snapshot': snapshot()}, 1))
        target_wire = BytesIO()
        serve(module.register, module.handle, source=wire, target=target_wire)
        registration, response = _responses(target_wire)
        assert len(registration['payload']['contributions']) == 24
        assert response['payload']['caseCount'] == 1 and response['payload']['runCount'] == 1
        assert response['payload']['executionAllowed'] is False
    finally:
        for key in list(sys.modules):
            if key == name or key.startswith(name + '.'):
                del sys.modules[key]
