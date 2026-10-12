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


@pytest.mark.parametrize('method', ['POST', 'PUT', 'PATCH', 'DELETE', 'TRACE', 'CONNECT'])
def test_management_readonly_blocks_mutations_before_product_app(entry, method):
    from starlette.testclient import TestClient
    async def product(scope, receive, send):
        pytest.fail('management mutation reached product app')
    response = TestClient(entry.ReadOnlyManagementApp(product)).request(method, '/v1/auth/token')
    assert response.status_code == 405
    assert response.json()['code'] == 'RESTORED_MANAGEMENT_READ_ONLY'


def test_management_reads_delegate_without_fabricating_auth(entry):
    from starlette.testclient import TestClient
    observed = []
    async def product(scope, receive, send):
        observed.append(scope['method'])
        await send({'type':'http.response.start','status':401,'headers':[]})
        await send({'type':'http.response.body','body':b''})
    client = TestClient(entry.ReadOnlyManagementApp(product))
    for method in ['GET','HEAD','OPTIONS']:
        assert client.request(method, '/v1/me').status_code == 401
    assert observed == ['GET','HEAD','OPTIONS']


def test_explicit_password_login_delegates_only_original_auth_endpoint(entry):
    from starlette.testclient import TestClient
    observed = []
    async def product(scope, receive, send):
        observed.append((scope['method'], scope['path']))
        await send({'type':'http.response.start','status':401,'headers':[]})
        await send({'type':'http.response.body','body':b''})
    client = TestClient(entry.ReadOnlyManagementApp(product, allow_password_login=True))
    assert client.post('/v1/auth/token', json={'grantType':'password'}).status_code == 401
    for path in ['/v1/auth/token/other', '/v1/auth/token/', '/v1/bundle-installations/x/approve']:
        assert client.post(path).status_code == 405
    assert client.put('/v1/auth/token').status_code == 405
    assert observed == [('POST', '/v1/auth/token')]


def test_owned_exact_local_oidc_config(entry, tmp_path):
    import json
    tmp_path.chmod(0o700)
    value = {'schemaVersion':'aos.local-management-oidc/v1',
        'issuer':'http://127.0.0.1:18448/realms/qyh-local', 'audience':'aos-api', 'clientId':'aos-api',
        'jwksUrl':'http://127.0.0.1:18448/realms/qyh-local/protocol/openid-connect/certs',
        'tokenUrl':'http://127.0.0.1:18448/realms/qyh-local/protocol/openid-connect/token',
        'clockSkewSeconds':2}
    p = tmp_path / 'oidc.json'; p.write_text(json.dumps(value)); p.chmod(0o600)
    assert entry.load_management_oidc_config(p)['AOS_AUTH_ALLOW_DEV'] == '0'
    assert entry.load_management_oidc_config(p)['AOS_OIDC_LEEWAY_SECONDS'] == '2'
    for key, bad in [('issuer','http://other-host/realms/qyh-local'), ('clockSkewSeconds',True),
                     ('clockSkewSeconds',6), ('audience','other'), ('tokenUrl','http://127.0.0.1:18448/other')]:
        p.write_text(json.dumps({**value, key:bad}))
        with pytest.raises(entry.RestorationBlocked): entry.load_management_oidc_config(p)
    p.write_text(json.dumps(value)); p.chmod(0o644)
    with pytest.raises(entry.RestorationBlocked): entry.load_management_oidc_config(p)


def test_local_oidc_rejects_duplicate_symlink_fifo_and_extra_fields(entry, tmp_path):
    import json, os
    tmp_path.chmod(0o700)
    value = {'schemaVersion':'aos.local-management-oidc/v1',
        'issuer':'http://127.0.0.1:18448/realms/qyh-local', 'audience':'aos-api', 'clientId':'aos-api',
        'jwksUrl':'http://127.0.0.1:18448/realms/qyh-local/protocol/openid-connect/certs',
        'tokenUrl':'http://127.0.0.1:18448/realms/qyh-local/protocol/openid-connect/token',
        'clockSkewSeconds':2}
    p = tmp_path / 'config.json'; p.write_text(json.dumps(value)); p.chmod(0o600)
    alias = tmp_path / 'alias.json'; alias.symlink_to(p)
    with pytest.raises(entry.RestorationBlocked): entry.load_management_oidc_config(alias)
    fifo = tmp_path / 'fifo'; os.mkfifo(fifo, 0o600)
    with pytest.raises(entry.RestorationBlocked): entry.load_management_oidc_config(fifo)
    p.write_text(json.dumps({**value,'password':'must-not-be-configured-here'}))
    with pytest.raises(entry.RestorationBlocked): entry.load_management_oidc_config(p)
    p.write_text(json.dumps(value)[:-1] + ',"clockSkewSeconds":0}')
    with pytest.raises(entry.RestorationBlocked): entry.load_management_oidc_config(p)


def test_login_optin_does_not_accept_truthy_nonboolean(entry):
    from starlette.testclient import TestClient
    async def product(*args): pytest.fail('truthy flag enabled a write')
    client = TestClient(entry.ReadOnlyManagementApp(product, allow_password_login='true'))
    assert client.post('/v1/auth/token').status_code == 405


def test_local_login_config_requires_management_start(entry, monkeypatch, tmp_path):
    monkeypatch.setattr('sys.argv',['entry','--api-identity-file',str(tmp_path/'identity'),
        '--management-oidc-config',str(tmp_path/'oidc')])
    with pytest.raises(SystemExit) as exc: entry.main()
    assert exc.value.code == 2


def test_management_websocket_never_reaches_product(entry):
    import asyncio
    observed = []
    async def product(*args):
        pytest.fail('management WebSocket reached product')
    async def send(event): observed.append(event)
    asyncio.run(entry.ReadOnlyManagementApp(product)({'type':'websocket'}, None, send))
    assert observed == [{'type':'websocket.close','code':1008}]


def test_management_preserves_product_lifespan(entry):
    import asyncio
    calls = []
    async def product(scope, receive, send):
        calls.append(scope['type'])
        await send({'type':'lifespan.startup.complete'})
    async def send(event): calls.append(event['type'])
    asyncio.run(entry.ReadOnlyManagementApp(product)({'type':'lifespan'}, None, send))
    assert calls == ['lifespan', 'lifespan.startup.complete']


def test_management_and_formal_runtime_start_are_mutually_exclusive(entry, monkeypatch, tmp_path):
    monkeypatch.setattr('sys.argv', ['entry','--api-identity-file',str(tmp_path/'identity'),
        '--serve-management-readonly','--serve-limited'])
    monkeypatch.setattr(entry,'serve_management_readonly',lambda **kw:pytest.fail('ambiguous start accepted'))
    with pytest.raises(SystemExit) as exc:
        entry.main()
    assert exc.value.code == 2


def test_management_start_uses_fresh_interpreter_and_frozen_factory(entry):
    import sys
    command = entry.management_command()
    assert command[:4] == [sys.executable, '-m', 'uvicorn', 'a0v_qyh_restored_http:management_app']
    assert '--factory' in command
    assert command[command.index('--host')+1] == '127.0.0.1'
    assert command[command.index('--workers')+1] == '1'

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


@pytest.mark.parametrize('schema', ['a0v_160', 'a0v_161'])
def test_migrated_preserved_cluster_matches_current_code(entry, schema):
    observed = {**baseline(), 'schema': schema, 'tables': 650}
    entry.require_identity(observed, code_head=schema)


@pytest.mark.parametrize('schema,tables', [
    ('a0v_159', 650), ('a0v_160', 647), ('a0v_161', 647),
    ('a0v_161', 649), ('a0v_161', 651), ('a0v_162', 650),
])
def test_unknown_or_partial_migration_never_attaches(entry, schema, tables):
    with pytest.raises(entry.RestorationBlocked, match='RESTORED_IDENTITY_DRIFT'):
        entry.require_identity({**baseline(), 'schema': schema, 'tables': tables},
            code_head=schema)


@pytest.mark.parametrize('field,value', [
    ('database', 'other'), ('cluster', 'other'), ('orgId', 'dev-org'),
    ('orgName', 'org-org'), ('projectId', 'other'),
])
def test_migrated_schema_keeps_original_tenant_and_volume_identity(entry, field, value):
    observed = {**baseline(), 'schema': 'a0v_161', 'tables': 650, field: value}
    with pytest.raises(entry.RestorationBlocked, match='RESTORED_IDENTITY_DRIFT'):
        entry.require_identity(observed, code_head='a0v_161')

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


def launch_arguments(tmp_path):
    return dict(identity_file=tmp_path/'identity.json', bundle_root=tmp_path/'bundles',
        trust_roots_file=tmp_path/'trust.json', installation_id=selected_view().installation_id,
        source_candidate=tmp_path/'source.json')


@pytest.mark.parametrize('issuer', [None, 'http://idp.example.test',
    'https://localhost', 'https://user:secret@idp.example.test'])
def test_limited_start_rejects_missing_or_invalid_formal_login_before_database(entry, monkeypatch, tmp_path, issuer):
    for name in ['AOS_OIDC_JWKS_URLS','AOS_OIDC_JWKS_URL','AOS_OIDC_ISSUERS','AOS_OIDC_ISSUER','AOS_OIDC_AUDIENCE']:
        monkeypatch.delenv(name, raising=False)
    if issuer is not None:
        monkeypatch.setenv('AOS_OIDC_ISSUER', issuer)
        monkeypatch.setenv('AOS_OIDC_JWKS_URL', 'https://idp.example.test/jwks')
        monkeypatch.setenv('AOS_OIDC_AUDIENCE', 'aos-api')
    monkeypatch.setattr(entry, 'select_current_installation', lambda **kw: pytest.fail('database gate reached'))
    with pytest.raises(entry.RestorationBlocked, match='EXTERNAL_OIDC_CONFIG'):
        entry.prepare_limited_launch(**launch_arguments(tmp_path))


def formal_login(monkeypatch):
    monkeypatch.setenv('AOS_OIDC_ISSUER', 'https://idp.example.test')
    monkeypatch.setenv('AOS_OIDC_JWKS_URL', 'https://idp.example.test/jwks')
    monkeypatch.setenv('AOS_OIDC_AUDIENCE', 'aos-api')
    monkeypatch.delenv('AOS_OIDC_ISSUERS', raising=False)
    monkeypatch.delenv('AOS_OIDC_JWKS_URLS', raising=False)


def test_limited_start_does_not_reuse_occupied_port(entry, monkeypatch, tmp_path):
    formal_login(monkeypatch)
    monkeypatch.setattr(entry.previous, '_port_free', lambda port: False)
    monkeypatch.setattr(entry, 'select_current_installation', lambda **kw: pytest.fail('database gate reached'))
    with pytest.raises(entry.RestorationBlocked, match='RESTORED_HTTP_PORT_OCCUPIED'):
        entry.prepare_limited_launch(**launch_arguments(tmp_path))


def test_limited_launch_replaces_inherited_database_code_and_execution_environment(entry, monkeypatch, tmp_path):
    formal_login(monkeypatch)
    monkeypatch.setattr(entry.previous, '_port_free', lambda port: port == 18080)
    monkeypatch.setattr(entry, 'require_api_source_candidate', lambda path: tmp_path/'frozen')
    report = {'currentInstallation': {'installationId': selected_view().installation_id}}
    monkeypatch.setattr(entry, 'select_current_installation', lambda **kw: report)
    identity = dict(host='127.0.0.1', port=18446, dbname='aos_meta_head',
        user='qyh_restored_api_login', pgpassFile=str(tmp_path/'private-passfile'))
    (tmp_path/'bundles').mkdir()
    (tmp_path/'trust.json').write_text('{}')
    monkeypatch.setattr(entry, '_identity_parameters', lambda path: identity)
    for key, value in {'PGPASSWORD':'must-not-survive','PGHOST':'wrong',
        'AOS_DATABASE_URL':'wrong','PYTHONPATH':'untrusted','AOS_AUTH_ALLOW_DEV':'1',
        'AOS_EXTENSION_RUNTIME_HOST_ENABLED':'1','AOS_ECOM_CONTENT_WORKER_ENABLED':'true',
        'AOS_DB_MIGRATION_MODE':'auto'}.items():
        monkeypatch.setenv(key,value)
    command, environment, public = entry.prepare_limited_launch(**launch_arguments(tmp_path))
    assert command[-1] == 'warning' and '18080' in command and '8080' not in command
    assert 'PGPASSWORD' not in environment and 'PGHOST' not in environment
    assert 'must-not-survive' not in str(environment) and 'untrusted' not in environment['PYTHONPATH']
    assert environment['PGPASSFILE'] == str(tmp_path/'private-passfile')
    assert 'aos_meta_head' in environment['AOS_DATABASE_URL']
    assert environment['AOS_AUTH_ALLOW_DEV'] == '0' and environment['AOS_AUTH_EXTERNAL_ONLY'] == '1'
    assert environment['AOS_EXTENSION_RUNTIME_HOST_ENABLED'] == '0'
    assert environment['AOS_ECOM_CONTENT_WORKER_ENABLED'] == 'false'
    assert environment['AOS_DB_MIGRATION_MODE'] == 'disabled'
    assert public['runtimeAuthorized'] is False and public['eightPagesAccepted'] is False
    assert 'private-passfile' not in str(public) and 'AOS_DATABASE_URL' not in public


def test_frozen_source_candidate_cannot_accept_a_source_path_outside_task(entry, tmp_path):
    import json
    report = tmp_path/'candidate.json'
    report.write_text(json.dumps({'source':str(tmp_path/'outside')}))
    with pytest.raises(entry.RestorationBlocked, match='RESTORED_API_SOURCE_CANDIDATE_INVALID'):
        entry.require_api_source_candidate(report)


@pytest.fixture
def source_candidate(entry, monkeypatch, tmp_path):
    import hashlib, json, subprocess
    root = tmp_path/'fixture-repo';root.mkdir()
    def git(*args):
        return subprocess.check_output(['git','-c','commit.gpgsign=false',
            '-c','core.hooksPath=/dev/null','-c','user.name=Fixture',
            '-c','user.email=fixture@invalid',*args],cwd=root)
    git('init','-b','m1')
    files={'services/aos-api/aos_api/main.py': b'VALUE = 1\n',
        'scripts/a0v_current_preview_http.py': Path(entry.previous.__file__).read_bytes(),
        'scripts/a0v_qyh_restored_http.py': Path(entry.__file__).read_bytes()}
    for name,data in files.items():
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    git('add','.');git('commit','-m','isolated source fixture')
    head=git('rev-parse','HEAD').decode().strip()
    task=root/'.evidence/qyh-full-system-restoration-20261011';private=task/'private'
    source=private/('api-source-'+head);source.mkdir(parents=True,mode=0o700)
    for name,data in files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);path.chmod(0o600)
    for path in [source,*source.rglob('*')]:
        if path.is_dir():path.chmod(0o700)
    manifest=json.dumps({n:hashlib.sha256(d).hexdigest() for n,d in files.items()},sort_keys=True).encode()
    manifest_path=private/('api-manifest-'+head+'.json');manifest_path.write_bytes(manifest);manifest_path.chmod(0o600)
    report=task/'candidate.json';report.write_text(json.dumps({'head':head,'source':str(source),
        'outcome':'CURRENT_M1_API_SOURCE_CANDIDATE_FROZEN_NO_START',
        'fileCount':len(files),'manifestSha256':hashlib.sha256(manifest).hexdigest()}))
    monkeypatch.setattr(entry,'ROOT',root)
    return report, source, root, git


def test_frozen_source_candidate_matches_committed_api_not_worktree(entry, source_candidate):
    report,source,root,git=source_candidate
    (root/'services/aos-api/aos_api/main.py').write_text('UNCOMMITTED = True\n')
    assert entry.require_api_source_candidate(report)==source


@pytest.mark.parametrize('drift',['file','permissions','current-commit','restored-entry-commit'])
def test_frozen_source_candidate_rejects_drift_before_process_start(entry, source_candidate, drift):
    report,source,root,git=source_candidate
    if drift=='restored-entry-commit':
        (root/'scripts/a0v_qyh_restored_http.py').write_text('CHANGED = True\n')
        git('add','scripts/a0v_qyh_restored_http.py');git('commit','-m','isolated attachment entry change')
        reason='RESTORED_CURRENT_API_SOURCE_DRIFT'
    elif drift=='current-commit':
        (root/'services/aos-api/aos_api/main.py').write_text('CHANGED = True\n')
        git('add','services/aos-api/aos_api/main.py');git('commit','-m','isolated source change')
        reason='RESTORED_CURRENT_API_SOURCE_DRIFT'
    elif drift=='permissions':
        (source/'services/aos-api/aos_api/main.py').chmod(0o644)
        reason='RESTORED_API_SOURCE_PERMISSION_DRIFT'
    else:
        (source/'services/aos-api/aos_api/main.py').write_text('CHANGED = True\n')
        reason='RESTORED_API_SOURCE_FILES_DRIFT'
    with pytest.raises(entry.RestorationBlocked,match=reason):
        entry.require_api_source_candidate(report)
