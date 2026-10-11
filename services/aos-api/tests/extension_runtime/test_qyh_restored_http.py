"""Restored-volume identity gates fail closed before any API process starts."""
import importlib
import pytest
from pathlib import Path

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
