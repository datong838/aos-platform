import json
import os
from uuid import uuid4

import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.types.json import Jsonb

from test_ui_read_api_role_pg import api_role, admission, queue, attempt_case, database, SCOPE, pytestmark as pg_required
from aos_api.extension_runtime.ui_read_connection import ui_read_connection, CREDENTIAL_FILE
import aos_api.extension_runtime.ui_read_connection as module


def credentials(tmp_path, monkeypatch, *, role='ui_reader', dsn='private-sentinel'):
    path = tmp_path / 'ui-read.json'
    path.write_text(json.dumps(dict(schemaVersion='aos.runtime-ui-api-identity/v1', role=role, dsn=dsn)))
    path.chmod(0o600)
    monkeypatch.setenv(CREDENTIAL_FILE, str(path))
    return path


@pytest.mark.parametrize('defect', ['permissions', 'symlink', 'fifo', 'json', 'duplicate', 'missing', 'relative', 'extra', 'uid'])
def test_bad_identity_file_never_connects_or_exposes_content(tmp_path, monkeypatch, defect):
    path = credentials(tmp_path, monkeypatch)
    if defect == 'permissions': path.chmod(0o644)
    if defect == 'symlink':
        link = tmp_path / 'link'
        link.symlink_to(path)
        monkeypatch.setenv(CREDENTIAL_FILE, str(link))
    if defect == 'fifo': path.unlink(); os.mkfifo(path, 0o600)
    if defect == 'json': path.write_text('private-sentinel')
    if defect == 'duplicate': path.write_text('{"dsn":"private-sentinel","dsn":"other"}')
    if defect == 'missing': path.unlink()
    if defect == 'relative': monkeypatch.setenv(CREDENTIAL_FILE, 'relative.json')
    if defect == 'extra':
        value = json.loads(path.read_text()); value['extra'] = True; path.write_text(json.dumps(value))
    if defect == 'uid':
        uid = os.getuid(); monkeypatch.setattr(module.os, 'getuid', lambda: uid + 1)
    monkeypatch.setattr(module.psycopg, 'connect', lambda *a, **kw: pytest.fail('bad identity connected'))
    with pytest.raises(RuntimeError) as error:
        with ui_read_connection(scope=SCOPE, subject='reader'): pass
    assert 'private-sentinel' not in str(error.value)


@pg_required
@pytest.mark.parametrize('defect', [None, 'inherit', 'superuser', 'extra-role', 'admin-option', 'wrong-name'])
def test_actual_independent_identity_and_transaction_rollback(api_role, tmp_path, monkeypatch, defect):
    owner, request, schema, login = api_role
    owner.execute(sql.SQL('ALTER ROLE {} NOINHERIT').format(sql.Identifier(login)))
    if defect == 'inherit': owner.execute(sql.SQL('ALTER ROLE {} INHERIT').format(sql.Identifier(login)))
    if defect == 'superuser': owner.execute(sql.SQL('ALTER ROLE {} SUPERUSER').format(sql.Identifier(login)))
    if defect == 'extra-role': owner.execute(sql.SQL('GRANT pg_read_all_data TO {}').format(sql.Identifier(login)))
    if defect == 'admin-option': owner.execute(sql.SQL('GRANT aos_ui_read_api TO {} WITH ADMIN OPTION').format(sql.Identifier(login)))
    credentials(tmp_path, monkeypatch, role='wrong_name' if defect == 'wrong-name' else login,
                dsn=make_conninfo(host='127.0.0.1', port=18432, dbname='postgres', user=login))
    if defect:
        with pytest.raises(RuntimeError, match='not permitted'):
            with ui_read_connection(scope=SCOPE, subject='reader'): pytest.fail('bad identity admitted')
        return
    statement = sql.SQL('SELECT {}.extension_ui_read_enqueue_a0v_032(%s,%s,%s)').format(sql.Identifier(schema))
    with pytest.raises(ValueError, match='rollback probe'):
        with ui_read_connection(scope=SCOPE, subject='reader') as conn:
            conn.execute(statement, ('reader', 'rollback', Jsonb(request.model_dump(mode='json'))))
            raise ValueError('rollback probe')
    assert owner.execute('SELECT count(*) FROM extension_runtime_ui_read_request').fetchone() == (0,)
    with ui_read_connection(scope=SCOPE, subject='reader') as conn:
        assert conn.execute('SELECT current_user AS role').fetchone()['role'] == 'aos_ui_read_api'
        conn.execute(statement, ('reader', 'commit', Jsonb(request.model_dump(mode='json'))))
    assert owner.execute('SELECT count(*) FROM extension_runtime_ui_read_request').fetchone() == (1,)
