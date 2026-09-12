import json
import os
from pathlib import Path

import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.pq import TransactionStatus

from aos_api.ecommerce_growth_registration_connection import (
    configured_registration_connection, registration_connection,
)
import aos_api.ecommerce_growth_registration_connection as module
from test_dispatch_first_registration_atomic_pg import registered_db, receipt_db, database, pytestmark as pg_required


@pytest.fixture(autouse=True)
def no_configuration(monkeypatch):
    monkeypatch.delenv('AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE',raising=False)


def credentials(tmp_path,*,dsn='fixture-only',role='registration_fixture'):
    path=tmp_path/'registration.json'
    path.write_text(json.dumps(dict(schemaVersion='aos.ecommerce.registration-identity/v1',dsn=dsn,role=role)))
    path.chmod(0o600)
    return path


def test_default_is_disabled_without_fallback(monkeypatch):
    monkeypatch.setenv('AOS_EXTENSION_RUNTIME_DATABASE_URL','must-not-be-used')
    monkeypatch.setattr(module.psycopg,'connect',lambda *a,**kw:pytest.fail('connection forbidden'))
    assert configured_registration_connection() is None
    with pytest.raises(RuntimeError):
        with registration_connection():pass


@pytest.mark.parametrize('defect',['permissions','symlink','relative','json','extra','role','size','missing','duplicate','fifo','uid'])
def test_bad_file_is_safe_and_never_connects(tmp_path,monkeypatch,defect):
    path=credentials(tmp_path)
    if defect=='permissions':path.chmod(0o644)
    elif defect=='symlink':
        link=tmp_path/'link';link.symlink_to(path);path=link
    elif defect=='relative':path=Path('relative-file.json')
    elif defect=='json':path.write_text('private-sentinel')
    elif defect=='size':path.write_text('private-sentinel'*5000)
    elif defect=='missing':path.unlink()
    elif defect=='duplicate':path.write_text('{"dsn":"private-sentinel","dsn":"duplicate"}')
    elif defect=='fifo':path.unlink();os.mkfifo(path,0o600)
    elif defect=='uid':
        uid=os.getuid();monkeypatch.setattr(module.os,'getuid',lambda:uid+1)
    else:
        value=json.loads(path.read_text())
        if defect=='extra':value['password']='private-sentinel'
        else:value['role']='invalid role'
        path.write_text(json.dumps(value))
    monkeypatch.setenv('AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE',str(path))
    monkeypatch.setattr(module.psycopg,'connect',lambda *a,**kw:pytest.fail('invalid file connected'))
    with pytest.raises(RuntimeError) as error:
        with registration_connection():pass
    assert 'private-sentinel' not in str(error.value)


def test_selector_does_not_open_connection(tmp_path,monkeypatch):
    monkeypatch.setenv('AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE',str(credentials(tmp_path)))
    monkeypatch.setattr(module.psycopg,'connect',lambda *a,**kw:pytest.fail('selector connected'))
    assert configured_registration_connection() is registration_connection


@pg_required
@pytest.mark.parametrize('defect',[None,'superuser','role-mismatch','missing-runtime','extra-role','admin-option','inherit'])
def test_actual_database_identity_and_idle_delivery(registered_db,tmp_path,monkeypatch,defect):
    case=registered_db;owner=case.db.owner
    if defect!='missing-runtime':owner.execute(sql.SQL('GRANT aos_runtime TO {}').format(sql.Identifier(case.login)))
    if defect=='extra-role':owner.execute(sql.SQL('GRANT pg_read_all_data TO {}').format(sql.Identifier(case.login)))
    if defect=='admin-option':owner.execute(sql.SQL('GRANT aos_extension_maintainer TO {} WITH ADMIN OPTION').format(sql.Identifier(case.login)))
    if defect=='inherit':owner.execute(sql.SQL('ALTER ROLE {} INHERIT').format(sql.Identifier(case.login)))
    login='postgres' if defect=='superuser' else case.login
    path=credentials(tmp_path,dsn=make_conninfo(**{**case.db.pg,'user':login}),role='wrong_role' if defect=='role-mismatch' else login)
    monkeypatch.setenv('AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE',str(path))
    if defect is None:
        with registration_connection() as conn:
            assert conn.info.transaction_status==TransactionStatus.IDLE
            assert conn.execute('SELECT session_user AS name').fetchone()['name']==case.login
    else:
        with pytest.raises(RuntimeError,match='registration identity'):
            with registration_connection():pytest.fail('unsafe identity yielded')


def test_connection_failure_never_exposes_secret(tmp_path,monkeypatch):
    monkeypatch.setenv('AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE',str(credentials(tmp_path)))
    def fail(*a,**kw):raise ValueError('private-sentinel')
    monkeypatch.setattr(module.psycopg,'connect',fail)
    with pytest.raises(RuntimeError) as error:
        with registration_connection():pass
    assert 'private-sentinel' not in str(error.value)
