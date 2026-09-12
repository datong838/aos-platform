from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from psycopg.pq import TransactionStatus


@pytest.fixture(autouse=True)
def no_inherited_credential_reference(monkeypatch):
    monkeypatch.delenv('AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE', raising=False)


class _Connection:
    def __init__(self):
        self.info = SimpleNamespace(transaction_status=TransactionStatus.IDLE)
        self.read_only = False
        self.isolation_level = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def test_worker_connection_starts_idle_without_scope_or_sql(monkeypatch):
    from aos_api.extension_runtime import runtime_connections
    connection = _Connection()
    calls = []
    monkeypatch.setenv("AOS_EXTENSION_RUNTIME_DATABASE_URL", "runtime")
    monkeypatch.setattr(runtime_connections, "get_dsn", lambda: "web")
    monkeypatch.setattr(runtime_connections.psycopg, "connect", lambda *a, **k: calls.append((a, k)) or connection)
    with runtime_connections.runtime_worker_connection() as opened:
        assert opened is connection
    assert calls[0][1]["row_factory"] is not None


def test_worker_connection_requires_a_distinct_configured_identity(monkeypatch):
    from aos_api.extension_runtime import runtime_connections
    monkeypatch.delenv("AOS_EXTENSION_RUNTIME_DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="not configured"):
        with runtime_connections.runtime_worker_connection():
            pass
    monkeypatch.setenv("AOS_EXTENSION_RUNTIME_DATABASE_URL", "same")
    monkeypatch.setattr(runtime_connections, "get_dsn", lambda: "same")
    with pytest.raises(RuntimeError, match="differ"):
        with runtime_connections.runtime_worker_connection():
            pass


def test_directory_connection_requires_distinct_dsn_and_sets_read_only(monkeypatch):
    from aos_api.extension_runtime import runtime_connections
    monkeypatch.delenv("AOS_EXTENSION_DIRECTORY_DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="not configured"):
        with runtime_connections.runtime_directory_connection():
            pass
    monkeypatch.setenv("AOS_EXTENSION_DIRECTORY_DATABASE_URL", "same")
    monkeypatch.setattr(runtime_connections, "get_dsn", lambda: "same")
    with pytest.raises(RuntimeError, match="differ"):
        with runtime_connections.runtime_directory_connection():
            pass
    connection = _Connection()
    monkeypatch.setenv("AOS_EXTENSION_DIRECTORY_DATABASE_URL", "directory")
    monkeypatch.setattr(runtime_connections.psycopg, "connect", lambda *a, **k: connection)
    with runtime_connections.runtime_directory_connection() as opened:
        assert opened.read_only is True
        assert opened.isolation_level is not None


def credential_file(tmp_path):
    import json
    path=tmp_path/'identities.json'
    path.write_text(json.dumps({name:{'dsn':name,'password':'fixture-only','role':name} for name in ('web','runtime','directory')}))
    path.chmod(0o600)
    return path


def test_worker_uses_protected_credential_reference_without_secret_environment(monkeypatch,tmp_path):
    from aos_api.extension_runtime import runtime_connections
    path=credential_file(tmp_path)
    monkeypatch.setenv('AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE',str(path))
    monkeypatch.delenv('AOS_EXTENSION_RUNTIME_DATABASE_URL',raising=False)
    connection=_Connection();calls=[]
    monkeypatch.setattr(runtime_connections.psycopg,'connect',lambda *a,**kw:calls.append(a) or connection)
    with runtime_connections.runtime_worker_connection() as opened:assert opened is connection
    assert calls==[('runtime',)]


@pytest.mark.parametrize('mode',['permissions','symlink','malformed','same_identity'])
def test_bad_credential_reference_never_connects(monkeypatch,tmp_path,mode):
    import json
    from aos_api.extension_runtime import runtime_connections
    path=credential_file(tmp_path)
    if mode=='permissions':path.chmod(0o644)
    elif mode=='symlink':
        link=tmp_path/'link';link.symlink_to(path);path=link
    elif mode=='malformed':path.write_text('fixture-secret-invalid-json')
    else:
        data=json.loads(path.read_text());data['runtime']['dsn']=data['web']['dsn'];path.write_text(json.dumps(data))
    monkeypatch.setenv('AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE',str(path))
    monkeypatch.setenv('AOS_EXTENSION_RUNTIME_DATABASE_URL','legacy-must-not-be-fallback')
    monkeypatch.setattr(runtime_connections.psycopg,'connect',lambda *a,**kw:pytest.fail('bad identity connected'))
    with pytest.raises(RuntimeError) as error:
        with runtime_connections.runtime_worker_connection():pass
    assert 'fixture-secret' not in str(error.value)


@pytest.mark.parametrize('plane', ['runtime', 'directory', 'web'])
def test_all_planes_use_protected_reference(monkeypatch, tmp_path, plane):
    from aos_api.extension_runtime import runtime_connections as module
    path = credential_file(tmp_path)
    monkeypatch.setenv('AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE', str(path))
    monkeypatch.setattr(module, 'get_dsn', lambda: pytest.fail('legacy web fallback'))
    for name in ['AOS_EXTENSION_RUNTIME_DATABASE_URL', 'AOS_EXTENSION_DIRECTORY_DATABASE_URL']:
        monkeypatch.setenv(name, 'legacy-must-not-be-used')
    connection = _Connection()
    calls = []
    monkeypatch.setattr(module.psycopg, 'connect', lambda *a, **kw: calls.append(a) or connection)
    connector = {'runtime': module.runtime_worker_connection,
                 'directory': module.runtime_directory_connection,
                 'web': module.runtime_web_identity_connection}[plane]
    with connector() as opened:
        assert opened is connection
        assert opened.read_only is (plane == 'directory')
    assert calls == [(plane,)]


@pytest.mark.parametrize('plane', ['runtime', 'directory', 'web'])
@pytest.mark.parametrize('defect', ['bad_json', 'directory_role_equals_runtime', 'directory_dsn_equals_runtime'])
def test_bad_file_denies_every_plane_without_fallback(monkeypatch, tmp_path, plane, defect):
    import json
    from aos_api.extension_runtime import runtime_connections as module
    path = credential_file(tmp_path)
    value = json.loads(path.read_text())
    if defect == 'bad_json':
        path.write_text('private-fixture-invalid')
    else:
        key = 'role' if 'role' in defect else 'dsn'
        value['directory'][key] = value['runtime'][key]
        path.write_text(json.dumps(value))
    monkeypatch.setenv('AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE', str(path))
    monkeypatch.setenv('AOS_EXTENSION_DIRECTORY_DATABASE_URL', 'legacy-directory')
    monkeypatch.setenv('AOS_EXTENSION_RUNTIME_DATABASE_URL', 'legacy-runtime')
    monkeypatch.setattr(module, 'get_dsn', lambda: 'legacy-web')
    monkeypatch.setattr(module.psycopg, 'connect', lambda *a, **kw: pytest.fail('invalid file connected'))
    connector = {'runtime': module.runtime_worker_connection,
                 'directory': module.runtime_directory_connection,
                 'web': module.runtime_web_identity_connection}[plane]
    with pytest.raises(RuntimeError) as error:
        with connector():
            pass
    assert 'private-fixture' not in str(error.value)


def test_worker_dsn_selection_never_returns_web_fallback(monkeypatch,tmp_path):
    from aos_api.extension_runtime import runtime_connections as module
    path=credential_file(tmp_path)
    monkeypatch.setenv('AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE',str(path))
    monkeypatch.setattr(module,'get_dsn',lambda:pytest.fail('protected reference must not read web environment'))
    assert module.runtime_worker_dsn()=='runtime'
    path.chmod(0o644)
    with pytest.raises(RuntimeError):module.runtime_worker_dsn()
