"""Clone-only a0v070 -> a0v071 rehearsal for refresh-aware unaccepted closure."""
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / '.aos-recovery-20260916/state/unaccepted-closure-refresh-continuation-clone'
CLONE = 'aos_unaccepted_closure_refresh_20260916_test'
TASK = 'SC4-5L6Y5F4-REFRESH-DEPLOY-20260916'
FILES = ('a0v_071_unaccepted_closure_after_configuration_refresh.py',)


def fingerprint(conn):
    from psycopg import sql
    rows = conn.execute("""SELECT tablename FROM pg_tables
        WHERE schemaname='public' AND tablename<>'alembic_version'
        ORDER BY tablename""").fetchall()
    result = {}
    for row in rows:
        name = row['tablename']
        summary = dict(conn.execute(sql.SQL(
            "SELECT count(*) AS count,"
            "md5(string_agg(md5(to_jsonb(t)::text),'' ORDER BY md5(to_jsonb(t)::text))) AS digest "
            "FROM {} t"
        ).format(sql.Identifier('public', name))).fetchone())
        result[name] = summary
    return result


def verify(conn):
    function = conn.execute("""SELECT p.prosecdef,p.proconfig,
        has_function_privilege('aos_runtime',p.oid,'EXECUTE') AS runtime_execute,
        has_function_privilege('aos_extension_maintainer',p.oid,'EXECUTE') AS maintainer_execute,
        EXISTS(SELECT 1 FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
          WHERE a.grantee=0 AND a.privilege_type='EXECUTE') AS public_execute
        FROM pg_proc p WHERE p.oid=to_regprocedure(
          'public.ecommerce_unaccepted_analysis_close_a0v_060(jsonb,text)')""").fetchone()
    expected = dict(prosecdef=True,
        proconfig=['search_path=pg_catalog, public, pg_temp'],
        runtime_execute=False,maintainer_execute=True,public_execute=False)
    if function is None or dict(function) != expected:
        raise ValueError('event-control continuation function privilege/search_path differs')
    source = conn.execute("""SELECT pg_get_functiondef(to_regprocedure(
        'public.ecommerce_unaccepted_analysis_close_a0v_060(jsonb,text)')) AS body""").fetchone()['body']
    required = ('extension_dispatch_configuration_refresh_receipt',
        'refresh-proven closure runtime required',
        'configurationRefreshReceiptRef', 'targetConfigurationRef')
    if any(token not in source for token in required):
        raise ValueError('refresh-aware event-control continuation body differs')
    return dict(ownerFunction=expected,refreshAwareTokens=list(required))


def profile():
    path = Path(__file__).with_name('a0v_installed_bootstrap_action_deploy.py')
    spec = importlib.util.spec_from_file_location('dispatch_refresh_clone_base', path)
    deployment = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(deployment)
    deployment.STATE = STATE
    deployment.CLONE = CLONE
    deployment.TASK = TASK
    deployment.SOURCE = 'a0v_070'
    deployment.TARGET = 'a0v_071'
    deployment.FILES = FILES
    deployment.CHAIN = ['a0v_071']
    deployment.storage.CLONE = CLONE
    deployment.storage.FILES = FILES
    deployment.fingerprint = deployment.storage.fingerprint = fingerprint
    deployment.verify = verify
    deployment.executor_hashes = lambda: {
        file.name: deployment.storage.digest(file)
        for file in (Path(__file__), path, Path(deployment.storage.__file__), ROOT / 'services/aos-api/alembic/env.py')
    }
    original_upgrade = deployment.upgrade

    def clone_only_upgrade(database):
        if database != CLONE:
            raise ValueError('clone-only refresh migration required')
        return original_upgrade(database)

    deployment.upgrade = clone_only_upgrade
    return deployment


def prepare():
    from psycopg import sql
    deployment = profile()
    deployment.require_lease()
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE, 0o700)
    backup = STATE / 'aos_meta_head-before-a0v_071.dump'
    proof_path = STATE / 'prepare.json'
    if backup.exists() or proof_path.exists():
        raise ValueError('retained refresh clone preparation requires inspection')
    before, user, snapshot = deployment.snapshot_backup(backup)
    with deployment.storage.connect(deployment.storage.MAIN, autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0').format(sql.Identifier(CLONE)))
        conn.execute(sql.SQL('REVOKE CONNECT ON DATABASE {} FROM PUBLIC').format(sql.Identifier(CLONE)))
    with backup.open('rb') as handle:
        restored = subprocess.run([
            'docker', '--context', deployment.storage.CONTEXT, 'exec', '-i', deployment.storage.CONTAINER,
            'pg_restore', '-U', user, '-d', CLONE, '--exit-on-error',
        ], stdin=handle, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    if restored.returncode:
        raise RuntimeError('refresh clone restore failed; retained for inspection')
    with deployment.storage.connect(CLONE) as conn:
        if deployment.storage.version(conn) != ['a0v_070'] or fingerprint(conn) != before:
            raise ValueError('closure clone baseline differs')
    transaction = deployment.upgrade(CLONE)
    with deployment.storage.connect(CLONE) as conn:
        if deployment.storage.version(conn) != ['a0v_071'] or fingerprint(conn) != before:
            raise ValueError('closure clone final data differs')
        schema = verify(conn)
    proof = dict(
        outcome='UNACCEPTED_CLOSURE_REFRESH_CONTINUATION_CLONE_VERIFIED',
        source='a0v_070',
        target='a0v_071',
        main=deployment.storage.MAIN,
        clone=CLONE,
        migrations=deployment.storage.migration_hashes(),
        executors=deployment.executor_hashes(),
        backup=dict(path=str(backup), sha256=deployment.storage.digest(backup), bytes=backup.stat().st_size),
        snapshot=snapshot,
        before=before,
        after=transaction['after'],
        schema=schema,
        mainMigrated=False,
        businessWrites=0,
        sourceCalls=0,
        at=datetime.now(timezone.utc).isoformat(),
    )
    deployment.protected_write(proof_path, proof)
    with deployment.storage.connect(deployment.storage.MAIN) as conn:
        if deployment.storage.version(conn) != ['a0v_070']:
            raise ValueError('main version unexpectedly changed')
    public = {key: value for key, value in proof.items() if key not in ('before', 'after', 'snapshot', 'backup')}
    public.update(
        preservedTableCount=len(before),
        oldDataUnchanged=True,
        backupSha256=proof['backup']['sha256'],
    )
    evidence = ROOT / '.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/y5f4-unaccepted-closure-refresh-clone-verification.json'
    evidence.write_text(json.dumps(public, ensure_ascii=False, indent=2) + '\n')
    return public


if __name__ == '__main__':
    result = prepare()
    print(json.dumps({key: result[key] for key in ('outcome', 'preservedTableCount', 'mainMigrated')}))
