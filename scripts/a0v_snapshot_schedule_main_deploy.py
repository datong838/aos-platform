"""Fixed main migration after independently verified clone; existing intent is readback-only."""
from datetime import datetime,timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import a0v_snapshot_schedule_clone as clone

ROOT=clone.ROOT
STATE=ROOT.parent/'.aos-recovery-20260916/state/snapshot-schedule-main-deployment'
TASK='SC4-5L6Y6B-MAIN-MIGRATION-20260916'


def profile():
    path=ROOT/'scripts/a0v_installed_bootstrap_action_deploy.py'
    spec=importlib.util.spec_from_file_location('snapshot_main_transaction',path)
    p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
    p.STATE=STATE;p.TASK=TASK;p.CLONE=clone.CLONE;p.SOURCE='a0v_061';p.TARGET='a0v_066'
    p.FILES=clone.FILES;p.CHAIN=['a0v_066','a0v_065','a0v_064','a0v_063','a0v_062']
    p.storage.CLONE=clone.CLONE;p.storage.FILES=clone.FILES
    p.fingerprint=p.storage.fingerprint=clone.fingerprint;p.verify=clone.verify
    p.executor_hashes=lambda:dict(clone.profile().executor_hashes(),**{Path(__file__).name:p.storage.digest(Path(__file__))})
    return p


def validate_attestation(proof,migrations,executors,backup_digest):
    if (proof.get('outcome')!='SNAPSHOT_SCHEDULE_CLONE_RESTORE_VERIFIED'
        or proof.get('source')!='a0v_061' or proof.get('target')!='a0v_066'
        or proof.get('main')!='aos_meta_head' or proof.get('clone')!=clone.CLONE
        or proof.get('migrations')!=migrations or proof.get('executors')!=executors
        or not proof.get('before') or proof.get('before')!=proof.get('after')
        or proof.get('backup',{}).get('sha256')!=backup_digest):
        raise ValueError('verified clone attestation differs')


def private(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError('private retained file required')
    return path


def read_private(path):return json.loads(private(path).read_text())


def verify_clone(p):
    proof=read_private(clone.STATE/'prepare.json')
    backup=private(clone.STATE/'aos_meta_head-before-a0v_066.dump')
    if proof.get('backup',{}).get('path')!=str(backup):raise ValueError('backup path differs')
    validate_attestation(proof,p.storage.migration_hashes(),clone.profile().executor_hashes(),p.storage.digest(backup))
    with p.storage.connect(clone.CLONE) as c:
        c.execute('SET TRANSACTION READ ONLY')
        if p.storage.version(c)!=['a0v_066'] or clone.fingerprint(c)!=proof['before'] or clone.verify(c)!=proof['schema']:
            raise ValueError('retained clone changed')
    return proof


def backup_main(p):
    backup=STATE/'aos_meta_head-before-main-a0v_066.dump'
    with p.storage.connect(p.storage.MAIN) as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        if p.storage.version(c)!=['a0v_061']:raise ValueError('exact main source required')
        snapshot=c.execute('SELECT pg_export_snapshot() AS snapshot').fetchone()['snapshot']
        before=clone.fingerprint(c)
        with backup.open('xb') as handle:
            os.chmod(backup,0o600)
            result=subprocess.run(['docker','--context',p.storage.CONTEXT,'exec',p.storage.CONTAINER,
                'pg_dump','-U',c.info.user,'-d',p.storage.MAIN,'-Fc','--snapshot',snapshot],
                stdout=handle,stderr=subprocess.PIPE,timeout=120)
            handle.flush();os.fsync(handle.fileno())
        if result.returncode or not backup.stat().st_size:raise ValueError('fresh backup failed; retained')
    proof=dict(path=str(backup),sha256=p.storage.digest(backup),bytes=backup.stat().st_size,
               before=before,at=datetime.now(timezone.utc).isoformat())
    p.protected_write(STATE/'backup.json',proof)
    return proof


def readback(p):
    intent=read_private(STATE/'apply-intent.json')
    transaction=read_private(STATE/'transaction-verified.json')
    backup=read_private(STATE/'backup.json')
    path=private(STATE/'aos_meta_head-before-main-a0v_066.dump')
    if backup['path']!=str(path) or p.storage.digest(path)!=backup['sha256'] or path.stat().st_size!=backup['bytes']:
        raise ValueError('fresh backup changed')
    for proof in (intent,transaction):
        if (proof.get('source')!='a0v_061' or proof.get('target')!='a0v_066'
            or proof.get('migrations')!=p.storage.migration_hashes() or proof.get('executors')!=p.executor_hashes()):
            raise ValueError('main migration evidence changed')
    if not transaction.get('before') or transaction['before']!=transaction.get('after'):
        raise ValueError('original data preservation not proven')
    with p.storage.connect(p.storage.MAIN) as c:
        c.execute('SET TRANSACTION READ ONLY')
        if p.storage.version(c)!=['a0v_066']:raise ValueError('main commit unconfirmed; no retry')
        schema=clone.verify(c)
        # Migration stage must not have started any new snapshot group.
        from psycopg import sql
        for table in clone.NEW_TABLES:
            if c.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier('public',table))).fetchone()['n']:
                raise ValueError('new snapshot ledger not empty')
    result=dict(outcome='SNAPSHOT_SCHEDULE_MAIN_066_VERIFIED',source='a0v_061',target='a0v_066',
        preservedTableCount=len(transaction['before']),oldDataUnchangedWithinTransaction=True,
        migrations=p.storage.migration_hashes(),executors=p.executor_hashes(),schema=schema,
        freshBackupSha256=backup['sha256'],snapshotWorkerEnabled=False,sourceCalls=0,
        at=datetime.now(timezone.utc).isoformat())
    (ROOT/'.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/y6b-main-migration-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result


def apply():
    p=profile();p.require_lease();STATE.mkdir(parents=True,exist_ok=True,mode=0o700);os.chmod(STATE,0o700)
    verify_clone(p)
    if (STATE/'apply-intent.json').exists():return readback(p)
    if (STATE/'backup.json').exists():raise ValueError('retained backup requires inspection before new intent')
    backup_main(p)
    p.protected_write(STATE/'apply-intent.json',dict(source=p.SOURCE,target=p.TARGET,
        migrations=p.storage.migration_hashes(),executors=p.executor_hashes(),at=datetime.now(timezone.utc).isoformat()))
    p.upgrade(p.storage.MAIN)
    return readback(p)


if __name__=='__main__':
    result=apply()
    print(json.dumps({k:result[k] for k in ('outcome','preservedTableCount','snapshotWorkerEnabled','sourceCalls')}))
