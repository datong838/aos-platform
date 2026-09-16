"""Clone-only a0v072 -> a0v073 rehearsal for uninstalled predecessor registration."""
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess

import a0v_succeeded_disable_recovery_clone as prior


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / '.aos-recovery-20260916/state/uninstalled-successor-registration-clone'
CLONE = 'aos_uninstalled_successor_registration_20260916_test'
TASK = 'SC4-5L6Y5F4-REFRESH-DEPLOY-20260916'
FILES = ('a0v_073_uninstalled_successor_registration.py',)
fingerprint = prior.fingerprint


def verify(conn):
    row = conn.execute("""SELECT p.prosecdef,p.proconfig,
        has_function_privilege('aos_extension_maintainer',p.oid,'EXECUTE') AS maintainer_execute,
        has_function_privilege('aos_runtime',p.oid,'EXECUTE') AS runtime_execute,
        EXISTS(SELECT 1 FROM aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a
          WHERE a.grantee=0 AND a.privilege_type='EXECUTE') AS public_execute,
        p.prosrc AS body
        FROM pg_proc p WHERE p.oid=to_regprocedure(
          'public.extension_dispatch_successor_register_a0v_056(jsonb,text)')""").fetchone()
    expected = {'prosecdef': True, 'proconfig': ['search_path=pg_catalog, public, pg_temp'],
                'maintainer_execute': True, 'runtime_execute': False, 'public_execute': False}
    if row is None or {key: row[key] for key in expected} != expected:
        raise ValueError('successor registration privileges/search_path differ')
    required = ("v_old_binding.desired_state='uninstalled'",
        "v_old_binding.observed_state='stopped'", "r.state='uninstalled'",
        'i.active_revision IS NULL', "v_old_binding.desired_state='disabled'")
    if any(token not in row['body'] for token in required):
        raise ValueError('uninstalled successor registration body differs')
    return {'function': expected, 'requiredTokens': list(required)}


def profile():
    path = ROOT / 'scripts/a0v_installed_bootstrap_action_deploy.py'
    spec = importlib.util.spec_from_file_location('uninstalled_successor_clone_base', path)
    deployment = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(deployment)
    deployment.STATE, deployment.CLONE, deployment.TASK = STATE, CLONE, TASK
    deployment.SOURCE, deployment.TARGET = 'a0v_072', 'a0v_073'
    deployment.FILES, deployment.CHAIN = FILES, ['a0v_073']
    deployment.storage.CLONE, deployment.storage.FILES = CLONE, FILES
    deployment.fingerprint = deployment.storage.fingerprint = fingerprint
    deployment.verify = verify
    deployment.executor_hashes = lambda: {
        file.name: deployment.storage.digest(file)
        for file in (Path(__file__), path, Path(deployment.storage.__file__),
                     ROOT / 'services/aos-api/alembic/env.py')}
    original = deployment.upgrade
    def clone_only(database):
        if database != CLONE:
            raise ValueError('clone-only a0v073 migration required')
        return original(database)
    deployment.upgrade = clone_only
    return deployment


def prepare():
    from psycopg import sql
    deployment = profile()
    deployment.require_lease()
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup = STATE / 'aos_meta_head-before-a0v_073.dump'
    proof_path = STATE / 'prepare.json'
    if backup.exists() or proof_path.exists():
        raise ValueError('retained a0v073 clone preparation requires inspection')
    before, user, snapshot = deployment.snapshot_backup(backup)
    with deployment.storage.connect(deployment.storage.MAIN, autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0').format(sql.Identifier(CLONE)))
        conn.execute(sql.SQL('REVOKE CONNECT ON DATABASE {} FROM PUBLIC').format(sql.Identifier(CLONE)))
    with backup.open('rb') as handle:
        restored = subprocess.run(['docker', '--context', deployment.storage.CONTEXT, 'exec', '-i',
            deployment.storage.CONTAINER, 'pg_restore', '-U', user, '-d', CLONE, '--exit-on-error'],
            stdin=handle, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    if restored.returncode:
        raise RuntimeError('a0v073 clone restore failed; retained for inspection')
    with deployment.storage.connect(CLONE) as conn:
        if deployment.storage.version(conn) != ['a0v_072'] or fingerprint(conn) != before:
            raise ValueError('a0v073 clone baseline differs')
    transaction = deployment.upgrade(CLONE)
    with deployment.storage.connect(CLONE) as conn:
        if deployment.storage.version(conn) != ['a0v_073'] or fingerprint(conn) != before:
            raise ValueError('a0v073 clone final data differs')
        schema = verify(conn)
    proof = {'outcome': 'UNINSTALLED_SUCCESSOR_REGISTRATION_CLONE_VERIFIED',
        'source': 'a0v_072', 'target': 'a0v_073', 'main': deployment.storage.MAIN,
        'clone': CLONE, 'migrations': deployment.storage.migration_hashes(),
        'executors': deployment.executor_hashes(),
        'backup': {'path': str(backup), 'sha256': deployment.storage.digest(backup),
                   'bytes': backup.stat().st_size}, 'snapshot': snapshot,
        'before': before, 'after': transaction['after'], 'schema': schema,
        'mainMigrated': False, 'businessWrites': 0, 'sourceCalls': 0,
        'at': datetime.now(timezone.utc).isoformat()}
    deployment.protected_write(proof_path, proof)
    public = {key: value for key, value in proof.items()
              if key not in ('before', 'after', 'snapshot', 'backup')}
    public.update(preservedTableCount=len(before), oldDataUnchanged=True,
                  backupSha256=proof['backup']['sha256'])
    evidence = ROOT / '.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/y5f4-uninstalled-successor-registration-clone.json'
    evidence.write_text(json.dumps(public, ensure_ascii=False, indent=2) + '\n')
    return public


if __name__ == '__main__':
    result = prepare()
    print(json.dumps({key: result[key] for key in ('outcome', 'preservedTableCount', 'mainMigrated')}))
