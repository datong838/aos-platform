"""Restored-volume identity gates fail closed before any API process starts."""
import importlib
import pytest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[4]

@pytest.fixture
def entry(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'scripts'))
    return importlib.import_module('a0v_qyh_restored_http')

def baseline():
    return {'database': 'aos_meta_head', 'cluster': '7695302940039200809',
            'schema': 'a0v_159', 'orgId': 'org-org',
            'orgName': '栖月汇商贸有限公司', 'projectId': 'dev-project',
            'tables': 647}

@pytest.mark.parametrize('field,value', [
    ('database', 'aos_current_preview_20260927'), ('cluster', '7683855731447750695'),
    ('schema', 'a0v_092'), ('orgId', 'dev-org'), ('orgName', 'org-org'),
    ('projectId', 'other-project'), ('tables', 626)])
def test_wrong_database_or_tenant_rejected(entry, field, value):
    observed = baseline(); observed[field] = value
    with pytest.raises(entry.RestorationBlocked, match='RESTORED_IDENTITY_DRIFT'):
        entry.require_identity(observed, code_head='a0v_159')

def test_schema_must_match_current_code(entry):
    with pytest.raises(entry.RestorationBlocked, match='RESTORED_CODE_SCHEMA_DRIFT'):
        entry.require_identity(baseline(), code_head='a0v_160')

def test_preserved_data_does_not_grant_start_or_workshop_readiness(entry):
    entry.require_identity(baseline(), code_head='a0v_159')
    report = entry.inventory_report(baseline(), {'bindings': 126, 'installations': 135,
        'configurations': 130, 'enabledBindings': 0})
    assert report['apiStartAuthorized'] is False
    assert report['eightWorkbenchesVerified'] is False
    assert report['runtimeHostEnabled'] is False


def selected_view():
    versions = {'domain.ecommerce.core': '1.4.3', 'platform.ecommerce.niushop': '1.23.2',
                'solution.ecommerce.growth': '1.13.0', 'solution.ecommerce.operations-base': '1.2.2'}
    return SimpleNamespace(scope=('org-org', 'dev-project'),
        installation_id='11111111-1111-4111-8111-111111111111',
        authorization='EVIDENCE_ONLY_NO_START', current_revision=4, etag_version=7,
        releases=tuple(SimpleNamespace(publisher='aos', bundle_id=bid, version=version,
            content_hash='sha256:'+'a'*64) for bid, version in versions.items()))


@pytest.mark.parametrize('drift', ['old-growth', 'old-core', 'old-platform', 'old-operations',
    'missing', 'extra', 'duplicate', 'publisher', 'tenant', 'installation', 'authorization'])
def test_current_installation_cannot_use_historical_or_ambiguous_releases(entry, drift):
    view = selected_view()
    if drift.startswith('old-'):
        bid = {'old-growth':'solution.ecommerce.growth', 'old-core':'domain.ecommerce.core',
            'old-platform':'platform.ecommerce.niushop',
            'old-operations':'solution.ecommerce.operations-base'}[drift]
        next(r for r in view.releases if r.bundle_id == bid).version = '1.0.0'
    elif drift == 'missing':
        view.releases = view.releases[:-1]
    elif drift in {'extra', 'duplicate'}:
        view.releases += (SimpleNamespace(publisher='aos',
            bundle_id='other' if drift == 'extra' else 'domain.ecommerce.core',
            version='1.4.3', content_hash='sha256:'+'a'*64),)
    elif drift == 'publisher':
        view.releases[0].publisher = 'other'
    elif drift == 'tenant':
        view.scope = ('dev-org', 'dev-project')
    elif drift == 'installation':
        view.installation_id = '22222222-2222-4222-8222-222222222222'
    else:
        view.authorization = 'START_AUTHORIZED'
    with pytest.raises(entry.RestorationBlocked):
        entry.require_selected_installation(view,
            installation_id='11111111-1111-4111-8111-111111111111')


def test_exact_installation_evidence_does_not_grant_api_or_runtime_start(entry):
    view = selected_view()
    result = entry.require_selected_installation(view, installation_id=view.installation_id)
    assert result['growthVersion'] == '1.13.0'
    assert result['apiStartAuthorized'] is False
    assert result['runtimeHostEnabled'] is False
    assert result['currentConfigurationVerified'] is False
