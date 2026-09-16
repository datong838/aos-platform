"""Deploy a0v074 after exact clone verification and a fresh main backup."""
from datetime import datetime,timezone
import importlib.util,json,os
from pathlib import Path
import subprocess

import a0v_released_event_retirement_clone as clone

ROOT=clone.ROOT
STATE=ROOT.parent/'.aos-recovery-20260916/state/released-event-retirement-main'


def profile():
    path=ROOT/'scripts/a0v_installed_bootstrap_action_deploy.py'
    spec=importlib.util.spec_from_file_location('released_event_main_base',path)
    deployment=importlib.util.module_from_spec(spec);spec.loader.exec_module(deployment)
    deployment.STATE,deployment.TASK,deployment.CLONE=STATE,clone.TASK,clone.CLONE
    deployment.SOURCE,deployment.TARGET='a0v_073','a0v_074'
    deployment.FILES,deployment.CHAIN=clone.FILES,['a0v_074']
    deployment.storage.CLONE,deployment.storage.FILES=clone.CLONE,clone.FILES
    deployment.fingerprint=deployment.storage.fingerprint=clone.fingerprint;deployment.verify=clone.verify
    deployment.executor_hashes=lambda:dict(clone.profile().executor_hashes(),
        **{Path(__file__).name:deployment.storage.digest(Path(__file__))})
    return deployment


def private(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_mode&0o777!=0o600:
        raise ValueError('private retained file required')
    return path


def read_private(path):return json.loads(private(path).read_text())


def verify_clone(deployment):
    proof=read_private(clone.STATE/'prepare.json');backup=private(clone.STATE/'aos_meta_head-before-a0v_074.dump')
    expected={'outcome':'RELEASED_EVENT_RETIREMENT_CLONE_VERIFIED','source':'a0v_073',
        'target':'a0v_074','main':deployment.storage.MAIN,'clone':clone.CLONE,
        'migrations':deployment.storage.migration_hashes(),'executors':clone.profile().executor_hashes()}
    if any(proof.get(k)!=v for k,v in expected.items()) or not proof.get('before') \
            or proof['before']!=proof.get('after') or proof.get('backup',{}).get('path')!=str(backup) \
            or proof['backup'].get('sha256')!=deployment.storage.digest(backup) \
            or proof['backup'].get('bytes')!=backup.stat().st_size:
        raise ValueError('a0v074 clone attestation differs')
    with deployment.storage.connect(clone.CLONE) as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        if deployment.storage.version(conn)!=['a0v_074'] or clone.fingerprint(conn)!=proof['before'] \
                or clone.verify(conn)!=proof['schema']:
            raise ValueError('a0v074 retained clone changed')
    return proof


def backup_main(deployment):
    backup=STATE/'aos_meta_head-before-main-a0v_074.dump'
    with deployment.storage.connect(deployment.storage.MAIN) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        if deployment.storage.version(conn)!=['a0v_073']:raise ValueError('exact main a0v073 source required')
        snapshot=conn.execute('SELECT pg_export_snapshot() AS snapshot').fetchone()['snapshot']
        before=clone.fingerprint(conn)
        with backup.open('xb') as handle:
            os.chmod(backup,0o600)
            result=subprocess.run(['docker','--context',deployment.storage.CONTEXT,'exec',
                deployment.storage.CONTAINER,'pg_dump','-U',conn.info.user,'-d',deployment.storage.MAIN,
                '-Fc','--snapshot',snapshot],stdout=handle,stderr=subprocess.PIPE,timeout=180)
            handle.flush();os.fsync(handle.fileno())
        if result.returncode or not backup.stat().st_size:raise ValueError('fresh a0v074 backup failed')
    proof={'path':str(backup),'sha256':deployment.storage.digest(backup),'bytes':backup.stat().st_size,
        'before':before,'at':datetime.now(timezone.utc).isoformat()}
    deployment.protected_write(STATE/'backup.json',proof);return proof


def readback(deployment):
    intent=read_private(STATE/'apply-intent.json');transaction=read_private(STATE/'transaction-verified.json')
    backup=read_private(STATE/'backup.json');path=private(STATE/'aos_meta_head-before-main-a0v_074.dump')
    if backup['path']!=str(path) or deployment.storage.digest(path)!=backup['sha256'] \
            or path.stat().st_size!=backup['bytes']:raise ValueError('fresh a0v074 backup changed')
    for proof in (intent,transaction):
        if proof.get('source')!='a0v_073' or proof.get('target')!='a0v_074' \
                or proof.get('migrations')!=deployment.storage.migration_hashes() \
                or proof.get('executors')!=deployment.executor_hashes():
            raise ValueError('a0v074 main evidence changed')
    if not transaction.get('before') or transaction['before']!=transaction.get('after'):
        raise ValueError('a0v074 existing data preservation not proven')
    with deployment.storage.connect(deployment.storage.MAIN) as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        if deployment.storage.version(conn)!=['a0v_074'] or clone.fingerprint(conn)!=transaction['before']:
            raise ValueError('a0v074 main commit unconfirmed')
        schema=clone.verify(conn)
    result={'outcome':'RELEASED_EVENT_RETIREMENT_MAIN_074_VERIFIED','source':'a0v_073',
        'target':'a0v_074','preservedTableCount':len(transaction['before']),
        'oldDataUnchangedWithinTransaction':True,'migrations':deployment.storage.migration_hashes(),
        'executors':deployment.executor_hashes(),'schema':schema,'freshBackupSha256':backup['sha256'],
        'businessWrites':0,'sourceCalls':0,'at':datetime.now(timezone.utc).isoformat()}
    evidence=ROOT/'.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/sc4-5l6y5f4-v-a0v074-main.json'
    evidence.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result


def apply():
    deployment=profile();deployment.require_lease();STATE.mkdir(parents=True,exist_ok=True,mode=0o700)
    verify_clone(deployment)
    if (STATE/'apply-intent.json').exists():return readback(deployment)
    if (STATE/'backup.json').exists():raise ValueError('retained a0v074 backup requires inspection')
    backup_main(deployment)
    deployment.protected_write(STATE/'apply-intent.json',{'source':'a0v_073','target':'a0v_074',
        'migrations':deployment.storage.migration_hashes(),'executors':deployment.executor_hashes(),
        'at':datetime.now(timezone.utc).isoformat()})
    deployment.upgrade(deployment.storage.MAIN);return readback(deployment)


if __name__=='__main__':
    result=apply();print(json.dumps({k:result[k] for k in ('outcome','preservedTableCount')}))
