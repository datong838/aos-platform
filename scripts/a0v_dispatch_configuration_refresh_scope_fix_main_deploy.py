"""Exact a0v068 -> a0v069 main deployment after retained scope-fix clone verification."""
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess

import a0v_dispatch_configuration_refresh_scope_fix_clone as clone


ROOT = clone.ROOT
STATE = ROOT.parent / '.aos-recovery-20260916/state/dispatch-configuration-refresh-scope-fix-main'
TASK = clone.TASK


def profile():
    path = ROOT / 'scripts/a0v_installed_bootstrap_action_deploy.py'
    spec = importlib.util.spec_from_file_location('dispatch_refresh_main_base', path)
    deployment = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(deployment)
    deployment.STATE = STATE
    deployment.TASK = TASK
    deployment.CLONE = clone.CLONE
    deployment.SOURCE = 'a0v_068'
    deployment.TARGET = 'a0v_069'
    deployment.FILES = clone.FILES
    deployment.CHAIN = ['a0v_069']
    deployment.storage.CLONE = clone.CLONE
    deployment.storage.FILES = clone.FILES
    deployment.fingerprint = deployment.storage.fingerprint = clone.fingerprint
    deployment.verify = clone.verify
    deployment.executor_hashes = lambda: dict(
        clone.profile().executor_hashes(),
        **{Path(__file__).name: deployment.storage.digest(Path(__file__))},
    )
    return deployment


def private(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError('private retained file required')
    return path


def read_private(path):
    return json.loads(private(path).read_text())


def verify_clone(deployment):
    proof = read_private(clone.STATE / 'prepare.json')
    backup = private(clone.STATE / 'aos_meta_head-before-a0v_069.dump')
    expected = dict(
        outcome='DISPATCH_CONFIGURATION_REFRESH_SCOPE_FIX_CLONE_VERIFIED',
        source='a0v_068',
        target='a0v_069',
        main=deployment.storage.MAIN,
        clone=clone.CLONE,
        migrations=deployment.storage.migration_hashes(),
        executors=clone.profile().executor_hashes(),
    )
    if any(proof.get(key) != value for key, value in expected.items()):
        raise ValueError('verified refresh clone attestation differs')
    if (
        not proof.get('before')
        or proof.get('before') != proof.get('after')
        or proof.get('backup', {}).get('path') != str(backup)
        or proof['backup'].get('sha256') != deployment.storage.digest(backup)
        or proof['backup'].get('bytes') != backup.stat().st_size
    ):
        raise ValueError('retained refresh clone proof changed')
    with deployment.storage.connect(clone.CLONE) as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        if (
            deployment.storage.version(conn) != ['a0v_069']
            or clone.fingerprint(conn) != proof['before']
            or clone.verify(conn) != proof['schema']
        ):
            raise ValueError('retained refresh clone changed')
    return proof


def backup_main(deployment):
    backup = STATE / 'aos_meta_head-before-main-a0v_069.dump'
    with deployment.storage.connect(deployment.storage.MAIN) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        if deployment.storage.version(conn) != ['a0v_068']:
            raise ValueError('exact main a0v068 source required')
        snapshot = conn.execute('SELECT pg_export_snapshot() AS snapshot').fetchone()['snapshot']
        before = clone.fingerprint(conn)
        with backup.open('xb') as handle:
            os.chmod(backup, 0o600)
            result = subprocess.run([
                'docker', '--context', deployment.storage.CONTEXT, 'exec', deployment.storage.CONTAINER,
                'pg_dump', '-U', conn.info.user, '-d', deployment.storage.MAIN, '-Fc', '--snapshot', snapshot,
            ], stdout=handle, stderr=subprocess.PIPE, timeout=180)
            handle.flush()
            os.fsync(handle.fileno())
        if result.returncode or not backup.stat().st_size:
            raise ValueError('fresh main refresh backup failed; retained')
    proof = dict(
        path=str(backup),
        sha256=deployment.storage.digest(backup),
        bytes=backup.stat().st_size,
        before=before,
        at=datetime.now(timezone.utc).isoformat(),
    )
    deployment.protected_write(STATE / 'backup.json', proof)
    return proof


def readback(deployment):
    intent = read_private(STATE / 'apply-intent.json')
    transaction = read_private(STATE / 'transaction-verified.json')
    backup = read_private(STATE / 'backup.json')
    path = private(STATE / 'aos_meta_head-before-main-a0v_069.dump')
    if backup['path'] != str(path) or deployment.storage.digest(path) != backup['sha256'] or path.stat().st_size != backup['bytes']:
        raise ValueError('fresh main refresh backup changed')
    for proof in (intent, transaction):
        if (
            proof.get('source') != 'a0v_068'
            or proof.get('target') != 'a0v_069'
            or proof.get('migrations') != deployment.storage.migration_hashes()
            or proof.get('executors') != deployment.executor_hashes()
        ):
            raise ValueError('main refresh migration evidence changed')
    if not transaction.get('before') or transaction['before'] != transaction.get('after'):
        raise ValueError('main refresh existing-data preservation not proven')
    with deployment.storage.connect(deployment.storage.MAIN) as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        if deployment.storage.version(conn) != ['a0v_069']:
            raise ValueError('main refresh commit unconfirmed; no retry')
        if clone.fingerprint(conn) != transaction['before']:
            raise ValueError('main refresh post-commit business fingerprint differs')
        schema = clone.verify(conn)
    result = dict(
        outcome='DISPATCH_CONFIGURATION_REFRESH_MAIN_069_VERIFIED',
        source='a0v_068',
        target='a0v_069',
        preservedTableCount=len(transaction['before']),
        oldDataUnchangedWithinTransaction=True,
        migrations=deployment.storage.migration_hashes(),
        executors=deployment.executor_hashes(),
        schema=schema,
        freshBackupSha256=backup['sha256'],
        refreshRows=0,
        businessWrites=0,
        sourceCalls=0,
        at=datetime.now(timezone.utc).isoformat(),
    )
    evidence = ROOT / '.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/y5f4-scope-fix-main-verification.json'
    evidence.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result


def apply():
    deployment = profile()
    deployment.require_lease()
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE, 0o700)
    verify_clone(deployment)
    if (STATE / 'apply-intent.json').exists():
        return readback(deployment)
    if (STATE / 'backup.json').exists():
        raise ValueError('retained main refresh backup requires inspection before new intent')
    backup_main(deployment)
    deployment.protected_write(STATE / 'apply-intent.json', dict(
        source='a0v_068',
        target='a0v_069',
        migrations=deployment.storage.migration_hashes(),
        executors=deployment.executor_hashes(),
        at=datetime.now(timezone.utc).isoformat(),
    ))
    deployment.upgrade(deployment.storage.MAIN)
    return readback(deployment)


if __name__ == '__main__':
    result = apply()
    print(json.dumps({key: result[key] for key in ('outcome', 'preservedTableCount', 'refreshRows')}))
