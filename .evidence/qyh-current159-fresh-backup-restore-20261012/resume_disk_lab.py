"""Reconcile known failed tmpfs restore and restore the same backup in owned disk lab."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

OUT=Path(__file__).parent
LAB='qyh-current159-restore-lab-20261012'
VOLUME='aos-qyh-current159-restore-lab-20261012'
IMAGE='sha256:7e7dbab8d3b431a20793a6d99cb5a6bc84e44914309917f1bf5589a7568cdefd'
CONTEXT='colima-aos-extension'


def docker(*args,**kwargs):
    return subprocess.run(['docker','--context',CONTEXT,*args],check=True,**kwargs)


def save(name,value):
    with (OUT/name).open('x') as f:json.dump(value,f,indent=2)


if __name__=='__main__':
    assert not (OUT/'lab-intent.json').exists(), 'Existing lab attempt must be reconciled only'
    spec=importlib.util.spec_from_file_location('backup',OUT/'backup_restore.py');backup=importlib.util.module_from_spec(spec);spec.loader.exec_module(backup)
    before=json.loads((OUT/'current-baseline.json').read_text())
    assert backup.source_fingerprint()==before
    archive=OUT/'private/copy/current.dump';expected=json.loads((OUT/'backup-terminal.json').read_text())['backupSHA256']
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==expected
    assert docker('container','ls','-a','--filter','name=^/'+LAB+'$','--format','{{.ID}}',capture_output=True,text=True).stdout.strip()==''
    assert docker('volume','ls','--filter','name=^'+VOLUME+'$','--format','{{.Name}}',capture_output=True,text=True).stdout.strip()==''
    save('lab-intent.json',{'container':LAB,'volume':VOLUME,'image':IMAGE,'network':'none','ports':[],
        'task':'qyh-current159-fresh-backup-restore-20261012','backupSHA256':expected,'actualAuthorityReplaced':False})
    docker('volume','create','--label','aos.task=qyh-current159-fresh-backup-restore-20261012',VOLUME,capture_output=True)
    cid=docker('run','-d','--name',LAB,'--network','none','--label','aos.task=qyh-current159-fresh-backup-restore-20261012',
        '-e','POSTGRES_USER=qyh_restore_lab_admin','-e','POSTGRES_DB=postgres','-e','POSTGRES_HOST_AUTH_METHOD=trust',
        '-v',VOLUME+':/var/lib/postgresql/data',IMAGE,capture_output=True,text=True).stdout.strip()
    save('lab-created.json',{'containerId':cid,'volume':VOLUME})
    for _ in range(30):
        ready=subprocess.run(['docker','--context',CONTEXT,'exec',LAB,'pg_isready','-U','qyh_restore_lab_admin','-d','postgres'],capture_output=True)
        if ready.returncode==0:break
        time.sleep(1)
    else:raise RuntimeError('Owned lab not ready: retain handle, do not create another')
    globals_path=OUT/'private/roles.sql'
    fd=os.open(globals_path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'wb') as f:
        docker('exec',backup.SOURCE,'pg_dumpall','--roles-only','--no-role-passwords','-U','aos_app',stdout=f,stderr=subprocess.PIPE)
    with globals_path.open('rb') as f:
        role_restore=docker('exec','-i',LAB,'psql','-X','-q','-v','ON_ERROR_STOP=1','-U','qyh_restore_lab_admin','-d','postgres',stdin=f,capture_output=True)
    docker('exec',LAB,'psql','-X','-q','-v','ON_ERROR_STOP=1','-U','qyh_restore_lab_admin','-d','postgres',
        '-c','CREATE DATABASE aos_meta_head OWNER aos_app',capture_output=True)
    save('disk-restore-intent.json',{'containerId':cid,'database':'aos_meta_head','sourceArchiveSHA256':expected,'networkNone':True,'replicaSubprocessOnly':True})
    with archive.open('rb') as f:
        result=subprocess.run(['docker','--context',CONTEXT,'exec','-i','-e','PGOPTIONS=-c session_replication_role=replica',LAB,
            'pg_restore','--exit-on-error','--single-transaction','-U','aos_app','-d','aos_meta_head'],stdin=f,capture_output=True)
    (OUT/'disk-restore.log').write_bytes(result.stdout+result.stderr)
    assert result.returncode==0, 'Known disk restore failure: reconcile, never replay blindly'
    source_after=backup.source_fingerprint();assert source_after==before
    backup.SOURCE=LAB
    restored=backup.source_fingerprint();assert restored==before
    save('result.json',{'backupSHA256':expected,'twoCopiesMatch':True,'freshCurrentSourceTables':len(before),
        'diskLabContainerId':cid,'diskLabVolume':VOLUME,'diskLabNetworkNone':True,'all647TableDataHashesAndCountsMatch':True,
        'actualSourceBeforeAfterUnchanged':True,'version':'a0v_159','actualAuthorityMigrated':False,
        'schemaACLAndSequencesFullyCompared':False,'continuousZeroExecutionWindowProven':False,'oldRunReplay':False})
    print(json.dumps({'freshCurrentSourceTables':len(before),'allDataHashesMatch':True,'sourceUnchanged':True,'diskLabNetwork':'none','actualMigration':False}))
