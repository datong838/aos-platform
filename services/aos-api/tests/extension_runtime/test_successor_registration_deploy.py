import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def deploy(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[4] / 'scripts'))
    return importlib.import_module('a0v_successor_registration_deploy')


def test_exact_deployment_scope(deploy):
    assert (deploy.SOURCE, deploy.TARGET, deploy.CHAIN) == ('a0v_055', 'a0v_056', ['a0v_056'])
    assert deploy.CLONE == 'aos_successor_registration_20260916_test'
    assert deploy.storage.MAIN == 'aos_meta_head'
    assert deploy.FILES == ('a0v_056_dispatch_successor_registration.py',)


def test_output_is_private_and_never_overwritten(deploy, tmp_path):
    path = tmp_path / 'proof.json'
    deploy.protected_write(path, {'first': True})
    with pytest.raises(FileExistsError):
        deploy.protected_write(path, {'first': False})
    assert json.loads(path.read_text()) == {'first': True}
    assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('bad', [{}, {'outcome': 'SUCCESSOR_REGISTRATION_RESTORE_VERIFIED', 'source': 'a0v_052'},
                                 {'outcome': 'SUCCESSOR_REGISTRATION_RESTORE_VERIFIED', 'source': 'a0v_053', 'target': 'a0v_055'}])
def test_wrong_preparation_never_reaches_database(deploy, bad):
    with pytest.raises(ValueError, match='preparation proof differs'):
        deploy.validate_proof(bad)


def test_existing_apply_intent_rejects_before_database(deploy, monkeypatch, tmp_path):
    monkeypatch.setattr(deploy, 'STATE', tmp_path)
    monkeypatch.setattr(deploy, 'require_lease', lambda: None)
    (tmp_path / 'apply-intent.json').write_text('{}')
    with pytest.raises(ValueError, match='existing intent'):
        deploy.apply()


@pytest.mark.parametrize('returncode', [0, 1])
def test_backup_and_fingerprint_share_live_snapshot(deploy, monkeypatch, tmp_path, returncode):
    from contextlib import contextmanager
    from types import SimpleNamespace
    events = []
    class Connection:
        info = SimpleNamespace(user='test_owner')
        def execute(self, query, args=None):
            events.append(query)
            if query.startswith('SELECT 1'):return SimpleNamespace(fetchone=lambda: None)
            if 'pg_export_snapshot' in query:
                return SimpleNamespace(fetchone=lambda: {'snapshot': '000001-000002-1'})
    @contextmanager
    def connect(database):
        events.append('opened')
        try:yield Connection()
        finally:events.append('closed')
    def dump(args, **kwargs):
        assert 'closed' not in events
        assert args[-2:] == ['--snapshot', '000001-000002-1']
        assert events.index('fingerprint') > events.index('SELECT pg_export_snapshot() AS snapshot')
        kwargs['stdout'].write(b'custom-format-backup')
        events.append('dump')
        return SimpleNamespace(returncode=returncode)
    monkeypatch.setattr(deploy.storage, 'connect', connect)
    monkeypatch.setattr(deploy.storage, 'version', lambda conn: [deploy.SOURCE])
    monkeypatch.setattr(deploy.storage, 'fingerprint', lambda conn: events.append('fingerprint') or {'existing': 1})
    monkeypatch.setattr(deploy.subprocess, 'run', dump)
    path = tmp_path / 'backup.dump'
    if returncode:
        with pytest.raises(RuntimeError, match='backup failed'):deploy.snapshot_backup(path)
    else:
        assert deploy.snapshot_backup(path) == ({'existing': 1}, 'test_owner', '000001-000002-1')
    assert events[1] == 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'
    assert events[-2:] == ['dump', 'closed']
    assert path.read_bytes() == b'custom-format-backup'
    assert path.stat().st_mode & 0o777 == 0o600

@pytest.mark.parametrize('mutates', [False, True])
def test_migration_transaction_distinguishes_concurrent_writes_from_own_dml(deploy, monkeypatch, tmp_path, mutates):
    """Real PostgreSQL + Alembic; isolated database, never the product database."""
    import os
    if os.getenv('AOS_EXTENSION_PG_TEST') != '1':pytest.skip('dedicated PostgreSQL opt-in required')
    from contextlib import contextmanager
    from uuid import uuid4
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
    from alembic import command
    root=tmp_path/'repo';alembic=root/'services/aos-api/alembic'
    (alembic/'versions').mkdir(parents=True)
    (root/'services/aos-api/alembic.ini').write_text('[alembic]\n')
    (alembic/'env.py').write_text((deploy.ROOT/'services/aos-api/alembic/env.py').read_text().replace('if config.config_file_name is not None:', 'if False:'))
    (alembic/'versions/base.py').write_text("revision='a0v_055'\ndown_revision=None\ndef upgrade():pass\n")
    body="op.execute('CREATE TABLE extension_dispatch_successor_registration_receipt(id integer)')"
    if mutates:body+="\n    op.execute('UPDATE existing_business SET value=99 WHERE id=1')"
    (alembic/'versions/target.py').write_text("from alembic import op\nrevision='a0v_056'\ndown_revision='a0v_055'\ndef upgrade():\n    "+body+'\n')
    db='aos056_tx_'+uuid4().hex[:12]
    params=dict(host='127.0.0.1',port=18434,user='aos_test',dbname=db)
    with psycopg.connect(**(params|{'dbname':'aos_test_admin'}),autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(db)))
    try:
        with psycopg.connect(**params) as conn:
            conn.execute("CREATE TABLE alembic_version(version_num text); INSERT INTO alembic_version VALUES('a0v_055'); CREATE TABLE existing_business(id integer PRIMARY KEY,value integer); INSERT INTO existing_business VALUES(1,0),(2,0)")
        @contextmanager
        def connect(database, autocommit=False):
            assert database==db
            with psycopg.connect(**params,row_factory=dict_row,autocommit=autocommit) as conn:yield conn
        monkeypatch.setattr(deploy,'ROOT',root)
        monkeypatch.setattr(deploy.storage,'connect',connect)
        monkeypatch.setattr(deploy.storage,'parameters',lambda database:dict(user='aos_test',password='',host='127.0.0.1',port=18434))
        monkeypatch.setattr(deploy.storage,'migration_hashes',lambda:{'test':'fixed'})
        monkeypatch.setattr(deploy,'executor_hashes',lambda:{'test':'fixed'})
        monkeypatch.setattr(deploy,'verify',lambda conn:{'empty':conn.execute('SELECT count(*) AS n FROM extension_dispatch_successor_registration_receipt').fetchone()['n']==0})
        original=command.upgrade
        def concurrent_then_upgrade(cfg,target):
            with psycopg.connect(**params) as other:
                other.execute('UPDATE existing_business SET value=7 WHERE id=2')
            return original(cfg,target)
        monkeypatch.setattr(command,'upgrade',concurrent_then_upgrade)
        if mutates:
            with pytest.raises(ValueError,match='migration changed existing data'):deploy.upgrade(db)
        else:
            proof=deploy.upgrade(db)
            assert proof['before']==proof['after'] and proof['schema']['empty']
        with psycopg.connect(**params) as conn:
            assert conn.execute('SELECT value FROM existing_business ORDER BY id').fetchall()==[(0,),(7,)]
            assert conn.execute('SELECT version_num FROM alembic_version').fetchone()[0]==('a0v_055' if mutates else 'a0v_056')
            assert (conn.execute("SELECT to_regclass('extension_dispatch_successor_registration_receipt')").fetchone()[0] is None)==mutates
    finally:
        with psycopg.connect(**(params|{'dbname':'aos_test_admin'}),autocommit=True) as admin:
            admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(db)))
