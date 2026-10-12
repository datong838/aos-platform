import json
import importlib.util
import os
from pathlib import Path
import sys
import subprocess
from contextlib import contextmanager

import pytest

from aos_api import aip_source_issuer_wiring as wiring
from aos_api.aip_bi_plan_issuer_connection import BIIssuerDatabaseBlocked
from aos_api.tenant_scope import TenantScope
from test_aip_source_issuer_connection_pg import issuer_case  # noqa: F401
from psycopg import sql


PURPOSE_ENV = {
    'plan': 'AOS_PLAN_SOURCE_ISSUER_CONFIG',
    'content': 'AOS_CONTENT_SOURCE_ISSUER_CONFIG',
    'contract': 'AOS_CONTRACT_SOURCE_ISSUER_CONFIG',
}


@pytest.fixture
def configured(tmp_path, monkeypatch):
    for key in PURPOSE_ENV.values():
        monkeypatch.delenv(key, raising=False)
    root = tmp_path / 'private'
    root.mkdir(mode=0o700)
    password_file = root / 'issuer.pgpass'
    password_file.write_text('unused isolated test placeholder\n')
    password_file.chmod(0o600)
    calls = []
    sentinel = object()

    @contextmanager
    def connection(config, scope):
        calls.append((config, scope))
        yield sentinel

    monkeypatch.setattr(wiring, 'connect_source_issuer_write', connection)
    monkeypatch.setattr(wiring, 'get_dsn', lambda: 'postgresql://aos_app@127.0.0.1:65535/isolated_source')

    def select(selected_purpose, **updates):
        payload = {'schemaVersion': 'aos.source-issuer-database/v1',
                   'purpose': selected_purpose, 'host': '127.0.0.1', 'port': 65535,
                   'database': 'isolated_source', 'passfile': str(password_file)}
        payload.update(updates)
        path = root / (selected_purpose + '.json')
        path.write_text(json.dumps(payload))
        path.chmod(0o600)
        monkeypatch.setenv(PURPOSE_ENV[selected_purpose], str(path))
        return path, wiring.configured_source_issuer_factory(selected_purpose)

    return select, calls, sentinel


@pytest.mark.parametrize('purpose', PURPOSE_ENV)
def test_unconfigured_keeps_original_store_default(monkeypatch, purpose):
    monkeypatch.delenv(PURPOSE_ENV[purpose], raising=False)
    assert wiring.configured_source_issuer_factory(purpose) is None


@pytest.mark.parametrize('purpose', PURPOSE_ENV)
def test_exact_purpose_and_caller_scope_use_original_connection(configured, purpose):
    select, calls, sentinel = configured
    _, factory = select(purpose)
    scope = TenantScope('org-org', 'dev-project')
    with factory(scope) as conn:
        assert conn is sentinel
    assert len(calls) == 1
    assert calls[0][0].purpose == purpose
    assert calls[0][1] is scope


@pytest.mark.parametrize('updates', [
    {'database': 'other_database'}, {'port': 65534}, {'host': '::1'},
    {'purpose': 'content'}, {'port': True}, {'password': 'forbidden-field'},
    {'role': 'aos_runtime'}, {'schemaVersion': 'unknown'},
])
def test_bad_explicit_config_never_connects_or_falls_back(configured, updates):
    select, calls, _ = configured
    _, factory = select('plan', **updates)
    with pytest.raises(BIIssuerDatabaseBlocked):
        with factory(TenantScope('org-org', 'dev-project')):
            pytest.fail('invalid configuration was accepted')
    assert calls == []


def test_public_config_permissions_are_rejected_before_connection(configured):
    select, calls, _ = configured
    path, factory = select('plan')
    path.chmod(0o644)
    with pytest.raises(BIIssuerDatabaseBlocked):
        with factory(TenantScope('org-org', 'dev-project')):
            pytest.fail('public configuration was accepted')
    assert calls == []


def test_duplicate_keys_are_rejected_before_connection(configured):
    select, calls, _ = configured
    path, factory = select('plan')
    raw = path.read_text()
    path.write_text(raw[:-1] + ',"purpose":"plan"}')
    with pytest.raises(BIIssuerDatabaseBlocked):
        with factory(TenantScope('org-org', 'dev-project')):
            pytest.fail('duplicate-key configuration was accepted')
    assert calls == []


def test_unknown_purpose_rejected_even_without_configuration():
    with pytest.raises(BIIssuerDatabaseBlocked):
        wiring.configured_source_issuer_factory('runtime')


def test_symlink_config_is_rejected_before_connection(configured):
    select, calls, _ = configured
    path, factory = select('plan')
    retained = path.with_suffix('.retained')
    path.rename(retained)
    path.symlink_to(retained)
    with pytest.raises(BIIssuerDatabaseBlocked):
        with factory(TenantScope('org-org', 'dev-project')):
            pytest.fail('symlink configuration was accepted')
    assert calls == []


def test_oversize_config_is_rejected_before_connection(configured):
    select, calls, _ = configured
    path, factory = select('plan')
    path.write_text(' ' * 16385)
    with pytest.raises(BIIssuerDatabaseBlocked):
        with factory(TenantScope('org-org', 'dev-project')):
            pytest.fail('oversize configuration was accepted')
    assert calls == []


def test_named_pipe_config_is_rejected_without_blocking(configured):
    select, _, _ = configured
    path, _ = select('plan')
    path.unlink()
    os.mkfifo(path, mode=0o600)
    code = """from aos_api.aip_source_issuer_wiring import configured_source_issuer_factory
from aos_api.aip_bi_plan_issuer_connection import BIIssuerDatabaseBlocked
from aos_api.tenant_scope import TenantScope
try:
    with configured_source_issuer_factory('plan')(TenantScope('org-org','dev-project')):
        raise AssertionError('named pipe accepted')
except BIIssuerDatabaseBlocked:
    print('NON_REGULAR_CONFIG_REJECTED')
"""
    result = subprocess.run([sys.executable, '-c', code], capture_output=True,
                            text=True, timeout=2, check=True)
    assert result.stdout.strip() == 'NON_REGULAR_CONFIG_REJECTED'


def test_invalid_application_target_does_not_leak_or_connect(configured, monkeypatch):
    select, calls, _ = configured
    _, factory = select('plan')
    monkeypatch.setattr(wiring, 'get_dsn', lambda: 'invalid target configuration')
    with pytest.raises(BIIssuerDatabaseBlocked, match='SOURCE_ISSUER_PRIVATE_EXACT_CONFIG_REQUIRED'):
        with factory(TenantScope('org-org', 'dev-project')):
            pytest.fail('invalid target was accepted')
    assert calls == []


@pytest.mark.parametrize(('module_name', 'attributes'), [
    ('aip_production_contracts', {'_plan_connect_factory': 'plan', '_contract_connect_factory': 'contract'}),
    ('aip_content_drafts', {'_connect': 'content'}),
    ('aip_responsibility_assignment', {'_plan_connect': 'plan'}),
])
def test_real_router_constructor_uses_each_original_source_factory(configured, monkeypatch, module_name, attributes):
    select, calls, sentinel = configured
    for purpose in set(attributes.values()):
        select(purpose)
    import aos_api.routers
    path = Path(aos_api.routers.__file__).parent / (module_name + '.py')
    isolated_name = 'aos_api.routers._source_wiring_test_' + module_name
    spec = importlib.util.spec_from_file_location(isolated_name, path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, isolated_name, module)
    spec.loader.exec_module(module)
    scope = TenantScope('org-org', 'dev-project')
    for attribute, purpose in attributes.items():
        with getattr(module._STORE, attribute)(scope) as conn:
            assert conn is sentinel
        assert calls[-1][0].purpose == purpose
        assert calls[-1][1] is scope


@pytest.mark.skipif(os.getenv('AOS_SOURCE_ISSUER_PG_TEST') != '1', reason='isolated native issuer opt-in required')
@pytest.mark.parametrize('purpose', PURPOSE_ENV)
def test_private_config_uses_actual_original_native_issuer_and_commits(issuer_case, monkeypatch, purpose):
    configs, schema, admin = issuer_case
    database = configs[purpose].database
    path = database.passfile.parent / (purpose + '-wiring.json')
    path.write_text(json.dumps({'schemaVersion': 'aos.source-issuer-database/v1',
        'purpose': purpose, 'host': database.host, 'port': database.port,
        'database': database.database, 'passfile': str(database.passfile)}))
    path.chmod(0o600)
    monkeypatch.setenv(PURPOSE_ENV[purpose], str(path))
    monkeypatch.setattr(wiring, 'get_dsn', lambda: 'postgresql://postgres@127.0.0.1:18432/postgres')
    scope = TenantScope('org-org', 'dev-project')
    factory = wiring.configured_source_issuer_factory(purpose)
    with factory(scope) as conn:
        assert conn.execute('SELECT session_user AS subject').fetchone()['subject'] == {
            'plan': 'aos_bi_plan_issuer', 'content': 'aos_content_source_issuer',
            'contract': 'aos_contract_source_issuer',
        }[purpose]
        conn.execute(sql.SQL('INSERT INTO {}.scoped VALUES(%s,%s,%s)').format(sql.Identifier(schema)),
                     (*scope.key, 'actual-wiring-commit'))
        conn.commit()
        assert conn.execute("SELECT current_setting('aos.org_id') AS org,current_setting('aos.project_id') AS project").fetchone() == {'org': scope.org_id, 'project': scope.project_id}
    assert admin.execute(sql.SQL('SELECT count(*) FROM {}.scoped WHERE value=%s').format(sql.Identifier(schema)), ('actual-wiring-commit',)).fetchone()[0] == 1
