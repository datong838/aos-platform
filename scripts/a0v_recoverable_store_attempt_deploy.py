#!/usr/bin/env python3
"""Back up and deploy only a0v088 to the isolated A0-V recovery database."""
from datetime import datetime, timezone
import hashlib, json, os, subprocess
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from psycopg import sql
from psycopg.rows import dict_row, tuple_row
from sqlalchemy import URL, create_engine

import a0v_controlled_source_claim_deploy as storage


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / '.aos-recovery-20260917/state/recoverable-store-attempt-deploy'
SOURCE, TARGET = 'a0v_087', 'a0v_088'
MIGRATION = ROOT / 'services/aos-api/alembic/versions/a0v_088_recoverable_store_attempt.py'
TABLES = ('extension_runtime_execution_attempt', 'extension_runtime_execution_attempt_event')


def digest(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'w') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write('\n'); handle.flush(); os.fsync(handle.fileno())


def fingerprint(conn):
    result = {}
    for table in TABLES:
        result[table] = dict(conn.execute(sql.SQL("""SELECT count(*) AS count,
          md5(coalesce(string_agg(md5(to_jsonb(t)::text),'' ORDER BY md5(to_jsonb(t)::text)),'')) AS digest
          FROM {} t""").format(sql.Identifier('public', table))).fetchone())
    return result


def verify(conn):
    constraint = conn.execute("""SELECT pg_get_constraintdef(oid) AS body FROM pg_constraint
      WHERE conrelid='public.extension_runtime_execution_attempt'::regclass
        AND conname='extension_runtime_execution_attempt_operation_kind_check'""").fetchone()
    trigger = conn.execute(
        "SELECT pg_get_functiondef('public.extension_runtime_attempt_insert_guard()'::regprocedure) AS body"
    ).fetchone()
    if (storage.version(conn) != [TARGET] or constraint is None or trigger is None
            or 'recoverable_store' not in constraint['body']
            or 'recoverable_store' not in trigger['body']):
        raise ValueError('a0v088 recoverable attempt readback differs')
    return {'version': [TARGET], 'recoverableStoreAttempt': True}


def apply():
    if subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip() != 'm1':
        raise ValueError('m1 single writer required')
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    if (STATE / 'result.json').exists():
        return json.loads((STATE / 'result.json').read_text(encoding='utf-8'))
    if any((STATE / name).exists() for name in ('backup.json', 'intent.json', 'transaction.json')):
        raise ValueError('partial deployment evidence requires inspection')
    cfg = Config(str(ROOT / 'services/aos-api/alembic.ini'))
    cfg.set_main_option('script_location', str(ROOT / 'services/aos-api/alembic'))
    directory = ScriptDirectory.from_config(cfg)
    if directory.get_heads() != [TARGET] or [r.revision for r in directory.iterate_revisions(TARGET, SOURCE)] != [TARGET]:
        raise ValueError('exact a0v088 migration chain required')
    migration_hash = digest(MIGRATION)
    with storage.connect(storage.MAIN) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        if storage.version(conn) != [SOURCE] or conn.execute('SELECT current_database() AS db').fetchone()['db'] != 'aos_meta_head':
            raise ValueError('exact isolated a0v087 source required')
        snapshot = conn.execute('SELECT pg_export_snapshot() AS snapshot').fetchone()['snapshot']
        before = fingerprint(conn)
        backup = STATE / 'aos_meta_head-before-a0v_088.dump'
        with backup.open('xb') as handle:
            os.chmod(backup, 0o600)
            outcome = subprocess.run(['docker', '--context', storage.CONTEXT, 'exec', storage.CONTAINER,
                'pg_dump', '-U', conn.info.user, '-d', storage.MAIN, '-Fc', '--snapshot', snapshot],
                stdout=handle, stderr=subprocess.PIPE, timeout=180)
            handle.flush(); os.fsync(handle.fileno())
        if outcome.returncode or not backup.stat().st_size:
            raise ValueError('fresh a0v088 backup failed')
    backup_proof = {'path': str(backup), 'bytes': backup.stat().st_size,
                    'sha256': digest(backup), 'before': before}
    write(STATE / 'backup.json', backup_proof)
    write(STATE / 'intent.json', {'source': SOURCE, 'target': TARGET,
        'migrationHash': migration_hash, 'at': datetime.now(timezone.utc).isoformat()})
    args = storage.parameters(storage.MAIN)
    url = URL.create('postgresql+psycopg', username=args['user'], password=args['password'],
        host=args['host'], port=int(args['port']), database=storage.MAIN,
        query={'options': '-c lock_timeout=5s -c statement_timeout=30s'})
    engine = create_engine(url, isolation_level='REPEATABLE READ')
    try:
        with engine.connect() as connection, connection.begin():
            raw = connection.connection.driver_connection; raw.row_factory = dict_row
            if storage.version(raw) != [SOURCE] or fingerprint(raw) != before:
                raise ValueError('pre-migration state changed')
            cfg.attributes['connection'] = connection; raw.row_factory = tuple_row
            try:
                command.upgrade(cfg, TARGET)
            finally:
                raw.row_factory = dict_row
            after = fingerprint(raw)
            if after != before:
                raise ValueError('a0v088 changed attempt authority rows')
            schema = verify(raw)
            transaction = {'source': SOURCE, 'target': TARGET, 'before': before,
                'after': after, 'migrationHash': migration_hash, 'schema': schema,
                'at': datetime.now(timezone.utc).isoformat()}
    finally:
        engine.dispose()
    write(STATE / 'transaction.json', transaction)
    with storage.connect(storage.MAIN) as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        if fingerprint(conn) != before:
            raise ValueError('post-commit attempt rows changed')
        schema = verify(conn)
    result = {'outcome': 'RECOVERABLE_STORE_ATTEMPT_088_GREEN', 'source': SOURCE,
        'target': TARGET, 'migrationHash': migration_hash,
        'backup': {key: backup_proof[key] for key in ('path', 'bytes', 'sha256')},
        'schema': schema, 'preservedTables': len(TABLES), 'businessWrites': 0,
        'sourceReads': 0, 'at': datetime.now(timezone.utc).isoformat()}
    write(STATE / 'result.json', result)
    return result


if __name__ == '__main__':
    print(json.dumps(apply(), ensure_ascii=False, indent=2))
