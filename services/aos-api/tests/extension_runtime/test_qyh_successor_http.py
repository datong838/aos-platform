import importlib
from pathlib import Path
import shutil
import pytest
ROOT=Path(__file__).resolve().parents[4]
@pytest.fixture
def m(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    return importlib.import_module('a0v_qyh_successor_http')


def args(tmp_path):
    return {k:tmp_path/k for k in ('build','build_receipt','qualification_receipt','signed_root','trust_roots_file','identity_file','source_candidate')} | {'installation_id':'11111111-1111-4111-8111-111111111111'}


def test_missing_oidc_before_source_installation_or_exec(m,monkeypatch,tmp_path):
    for k in m.OIDC_PUBLIC_ENV:monkeypatch.delenv(k,raising=False)
    monkeypatch.setattr(m.successor,'run',lambda **_:pytest.fail('installation before OIDC'))
    with pytest.raises(m.SuccessorHttpBlocked):m.prepare(**args(tmp_path))


@pytest.fixture
def prepared(m,monkeypatch,tmp_path):
    e=m.successor.load_entry()
    monkeypatch.setenv('AOS_OIDC_ISSUER','https://id.example.test');monkeypatch.setenv('AOS_OIDC_JWKS_URL','https://id.example.test/jwks');monkeypatch.setenv('AOS_OIDC_AUDIENCE','aos-api')
    monkeypatch.setattr(e.previous,'_port_free',lambda _:True)
    source=tmp_path/'frozen';source.mkdir()
    for file in m.LAUNCH_FILES:
        target=source/file;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/file,target)
    monkeypatch.setattr(e,'require_api_source_candidate',lambda _:source)
    monkeypatch.setattr(e,'_identity_parameters',lambda _:dict(host='127.0.0.1',port=18446,dbname='aos_meta_head',user='qyh_restored_api_login',pgpassFile='/existing-protected-passfile'))
    called=[]
    def run(**kwargs):
        called.append(kwargs);return {'currentInstallation':{'installationId':kwargs['installation_id']},'outcome':'ISOLATED_TEST_FIXTURE'}
    monkeypatch.setattr(m.successor,'run',run)
    monkeypatch.setattr(m.successor,'load_entry',lambda:e)
    a=args(tmp_path);a['signed_root'].mkdir();a['trust_roots_file'].write_text('{}')
    return e,source,a,called


def test_prepare_retains_all_gates_and_strips_protected_credentials(m,prepared,monkeypatch):
    e,source,a,called=prepared
    monkeypatch.setenv('AOS_RUNTIME_CONFIGURATION_STAGE_CREDENTIAL_FILE','/do-not-inherit')
    monkeypatch.setenv('AOS_OTHER_PROVIDER_KEY','fixture-not-secret')
    monkeypatch.setenv('PGPASSWORD','fixture-not-secret')
    monkeypatch.setenv('UNRELATED_ACCOUNT_TOKEN','fixture-not-secret')
    cmd,env,public=m.prepare(**a)
    assert len(called)==1 and called[0]['installation_id']==a['installation_id']
    assert 'AOS_RUNTIME_CONFIGURATION_STAGE_CREDENTIAL_FILE' not in env and 'AOS_OTHER_PROVIDER_KEY' not in env and 'PGPASSWORD' not in env
    assert 'UNRELATED_ACCOUNT_TOKEN' not in env
    assert env['AOS_AUTH_EXTERNAL_ONLY']=='1' and env['AOS_AUTH_ALLOW_DEV']=='0'
    assert env['AOS_EXTENSION_RUNTIME_HOST_ENABLED']=='0'
    assert 'default_transaction_read_only=on' in env['AOS_DATABASE_URL']
    assert '--factory' in cmd and 'a0v_qyh_successor_http:formal_readonly_app' in cmd
    assert public['runtimeAuthorized'] is False and public['mutationRequestsAllowed'] is False
    assert 'existing-protected' not in str(public)


def test_frozen_launch_module_drift_rejected(m,prepared):
    _,source,a,called=prepared
    (source/'scripts/a0v_qyh_successor_http.py').write_text('# wrong')
    with pytest.raises(m.SuccessorHttpBlocked,match='SOURCE'):m.prepare(**a)


def test_occupied_port_refuses_before_installation(m,prepared,monkeypatch):
    e,_,a,called=prepared;monkeypatch.setattr(e.previous,'_port_free',lambda _:False)
    with pytest.raises(m.SuccessorHttpBlocked):m.prepare(**a)
    assert not called


def test_factory_refuses_writable_or_wrong_database_before_connect(m,monkeypatch):
    import psycopg
    monkeypatch.setenv('AOS_AUTH_EXTERNAL_ONLY','1');monkeypatch.setenv('AOS_AUTH_ALLOW_DEV','0')
    monkeypatch.setenv('AOS_DATABASE_URL','host=127.0.0.1 port=18446 dbname=aos_meta_head user=qyh_restored_api_login')
    monkeypatch.setattr(psycopg,'connect',lambda *a,**k:pytest.fail('DB connection before read-only DSN validation'))
    with pytest.raises(m.SuccessorHttpBlocked,match='READONLY'):m.formal_readonly_app()


def test_factory_refuses_development_mode_before_database(m,monkeypatch):
    monkeypatch.setenv('AOS_AUTH_EXTERNAL_ONLY','0')
    with pytest.raises(m.SuccessorHttpBlocked,match='IDENTITY'):m.formal_readonly_app()


def test_factory_original_http_write_fence_and_actual_readonly_check(m,prepared,monkeypatch,tmp_path):
    import asyncio
    import psycopg
    import sys
    from types import SimpleNamespace
    _,source,a,_=prepared
    _,env,_=m.prepare(**a)
    for k,v in env.items():monkeypatch.setenv(k,v)
    passfile=tmp_path/'private-passfile';passfile.write_text('isolated-test-placeholder');passfile.chmod(0o600)
    monkeypatch.setenv('PGPASSFILE',str(passfile));monkeypatch.chdir(source)
    observations=[]
    class Connection:
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def execute(self,query):
            observations.append(query);return SimpleNamespace(fetchone=lambda:('on',))
    monkeypatch.setattr(psycopg,'connect',lambda *a,**k:Connection())
    async def app(scope,receive,send):pytest.fail('write/WS must not reach product app')
    monkeypatch.setitem(sys.modules,'aos_api.main',SimpleNamespace(app=app,__file__=str(source/'services/aos-api/aos_api/main.py')))
    guarded=m.formal_readonly_app()
    assert observations==['SHOW transaction_read_only']
    sent=[]
    async def send(value):sent.append(value)
    async def receive():return {}
    asyncio.run(guarded({'type':'http','method':'POST'},receive,send))
    assert sent[0]['status']==405
    sent.clear();asyncio.run(guarded({'type':'websocket'},receive,send))
    assert sent[0]['code']==1008
