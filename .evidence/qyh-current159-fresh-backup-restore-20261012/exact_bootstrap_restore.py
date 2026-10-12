"""Full isolated restore using the same bootstrap identity as the source cluster."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

OUT=Path(__file__).parent
LAB='qyh-current159-exact-restore-20261012'
VOLUME='aos-qyh-current159-exact-restore-20261012'
IMAGE='sha256:7e7dbab8d3b431a20793a6d99cb5a6bc84e44914309917f1bf5589a7568cdefd'


def run(*args,**kw):
    return subprocess.run(['docker','--context','colima-aos-extension',*args],check=True,**kw)


def save(name,value):
    with (OUT/name).open('x') as f:json.dump(value,f,indent=2)


if __name__=='__main__':
    assert not (OUT/'exact-lab-intent.json').exists()
    spec=importlib.util.spec_from_file_location('backup',OUT/'backup_restore.py');backup=importlib.util.module_from_spec(spec);spec.loader.exec_module(backup)
    before=json.loads((OUT/'current-baseline.json').read_text());assert backup.source_fingerprint()==before
    archive=OUT/'private/copy/current.dump';expected=json.loads((OUT/'backup-terminal.json').read_text())['backupSHA256']
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==expected
    assert run('container','ls','-a','--filter','name=^/'+LAB+'$','--format','{{.ID}}',capture_output=True,text=True).stdout.strip()==''
    assert run('volume','ls','--filter','name=^'+VOLUME+'$','--format','{{.Name}}',capture_output=True,text=True).stdout.strip()==''
    save('exact-lab-intent.json',{'container':LAB,'volume':VOLUME,'image':IMAGE,'bootstrap':'aos_app','network':'none','ports':[],
        'backupSHA256':expected,'sourceOrFailedLabsReplaced':False})
    run('volume','create','--label','aos.task=qyh-current159-fresh-backup-restore-20261012',VOLUME,capture_output=True)
    cid=run('run','-d','--name',LAB,'--network','none','--label','aos.task=qyh-current159-fresh-backup-restore-20261012',
        '-e','POSTGRES_USER=aos_app','-e','POSTGRES_DB=postgres','-e','POSTGRES_HOST_AUTH_METHOD=trust',
        '-v',VOLUME+':/var/lib/postgresql/data',IMAGE,capture_output=True,text=True).stdout.strip()
    save('exact-lab-created.json',{'containerId':cid,'volume':VOLUME})
    for _ in range(30):
        if subprocess.run(['docker','--context','colima-aos-extension','exec',LAB,'pg_isready','-U','aos_app','-d','postgres'],capture_output=True).returncode==0:break
        time.sleep(1)
    else:raise RuntimeError('Exact owned lab not ready; reconcile same handle')
    roles=(OUT/'private/roles.sql').read_text();assert roles.count('CREATE ROLE aos_app;')==1
    prepared=OUT/'private/exact-bootstrap-roles.sql';prepared.write_text(roles.replace('CREATE ROLE aos_app;','-- existing exact source bootstrap aos_app'))
    prepared.chmod(0o600)
    with prepared.open('rb') as f:
        result=subprocess.run(['docker','--context','colima-aos-extension','exec','-i',LAB,'psql','-X','-q','-v','ON_ERROR_STOP=1','-U','aos_app','-d','postgres'],stdin=f,capture_output=True)
    (OUT/'exact-role-restore.log').write_bytes(result.stdout+result.stderr)
    assert result.returncode==0
    run('exec',LAB,'psql','-X','-q','-v','ON_ERROR_STOP=1','-U','aos_app','-d','postgres','-c','CREATE DATABASE aos_meta_head OWNER aos_app',capture_output=True)
    save('exact-restore-intent.json',{'containerId':cid,'database':'aos_meta_head','backupSHA256':expected,'replicaModeSubprocessOnly':True})
    with archive.open('rb') as f:
        result=subprocess.run(['docker','--context','colima-aos-extension','exec','-i','-e','PGOPTIONS=-c session_replication_role=replica',LAB,
            'pg_restore','--single-transaction','--exit-on-error','-U','aos_app','-d','aos_meta_head'],stdin=f,capture_output=True)
    (OUT/'exact-restore.log').write_bytes(result.stdout+result.stderr)
    assert result.returncode==0, 'Restore failed; reconcile without replay'
    assert backup.source_fingerprint()==before
    backup.SOURCE=LAB;assert backup.source_fingerprint()==before
    save('result.json',{'backupSHA256':expected,'twoCopiesMatch':True,'exactBootstrap':'aos_app','ownedContainerId':cid,'ownedVolume':VOLUME,
        'networkNone':True,'ports':[],'all647TableDataHashesAndCountsMatch':True,'sourceUnchanged':True,
        'actualAuthorityMigrated':False,'actualServicesRestarted':False,'schemaACLAndSequencesFullyCompared':False,
        'continuousZeroExecutionWindowProven':False,'oldRunReplay':False})
    print(json.dumps({'exactCurrentRestoreTables':647,'allDataMatch':True,'sourceUnchanged':True,'actualMigration':False}))
