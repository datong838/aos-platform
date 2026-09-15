"""Retain an exact local database snapshot for model successor rehearsal."""
import os
from pathlib import Path
import subprocess
import a0v_historical_runtime_receipt_deploy as backup
from a0v_qyh_current_product_event_first_chain import freeze

CLONE = 'aos_model_successor_20260916_test'
STATE = Path(__file__).resolve().parents[2]/'.aos-recovery-20260916/state/model-successor-rehearsal'


def prepare():
    backup.CLONE = backup.storage.CLONE = CLONE
    backup.SOURCE = 'a0v_059'
    if STATE.exists():
        raise ValueError('existing rehearsal directory requires read-only inspection')
    STATE.mkdir(parents=True,mode=0o700)
    os.chmod(STATE,0o700)
    dump=STATE/'source.dump'
    before,user,snapshot=backup.snapshot_backup(dump)
    from psycopg import sql
    with backup.storage.connect(backup.storage.MAIN,autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0').format(sql.Identifier(CLONE)))
        conn.execute(sql.SQL('REVOKE CONNECT ON DATABASE {} FROM PUBLIC').format(sql.Identifier(CLONE)))
    with dump.open('rb') as stream:
        result=subprocess.run(['docker','--context',backup.storage.CONTEXT,'exec','-i',backup.storage.CONTAINER,
            'pg_restore','-U',user,'-d',CLONE,'--exit-on-error'],stdin=stream,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
    if result.returncode:
        raise RuntimeError('restore failed; retain clone and backup for inspection')
    with backup.storage.connect(CLONE) as conn:
        if backup.storage.version(conn)!=['a0v_059'] or backup.fingerprint(conn)!=before:
            raise ValueError('restored snapshot differs')
    freeze(STATE/'verified.json',dict(clone=CLONE,snapshot=snapshot,version='a0v_059',
        fingerprint=before,backupHash=backup.storage.digest(dump),providerCalls=0,mainWrites=0))
    return dict(outcome='MODEL_SUCCESSOR_CLONE_VERIFIED',clone=CLONE,mainWrites=0)


if __name__=='__main__':
    import json
    print(json.dumps(prepare()))
