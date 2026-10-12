"""Preserve restricted owned tmpfs labs, restoring their original HBA immediately."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile

OUT=Path(__file__).parent
CONTEXT='colima-aos-extension'


def run(name,*args,**kw):
    return subprocess.run(['docker','--context',CONTEXT,'exec',name,*args],check=True,**kw)


def psql(name,user,query):
    return run(name,'psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U',user,'-d','postgres','-c',query,capture_output=True,text=True).stdout.strip()


def save(name,value):
    with (OUT/name).open('x') as f:json.dump(value,f,indent=2)


if __name__=='__main__':
    before=json.loads((OUT/'before-containers.json').read_text())
    for name,r in before.items():
        if not r['Tmpfs'] or (OUT/(name+'-backup.json')).exists():continue
        intent=OUT/(name+'-backup-r2-intent.json');assert not intent.exists(), 'Reconcile r2 before retry'
        cid= subprocess.check_output(['docker','--context',CONTEXT,'inspect','--format','{{.Id}}',name],text=True).strip();assert cid==r['Id']
        user=run(name,'printenv','POSTGRES_USER',capture_output=True,text=True).stdout.strip()
        assert all(c.isalnum() or c=='_' for c in user)
        metadata=json.loads(psql(name,user,"BEGIN READ ONLY; SELECT json_build_object('cluster',(SELECT system_identifier::text FROM pg_control_system()),'databases',(SELECT json_agg(datname ORDER BY datname) FROM pg_database WHERE NOT datistemplate)); COMMIT;"))
        hba=psql(name,user,'SHOW hba_file');assert hba.startswith('/var/lib/postgresql/')
        original=run(name,'cat',hba,capture_output=True).stdout
        original_path=OUT/'private'/(name+'-original-pg_hba.conf')
        fd=os.open(original_path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'wb') as f:f.write(original)
        archive=OUT/'private'/(name+'-r2.tar')
        save(name+'-backup-r2-intent.json',{'containerId':cid,'metadata':metadata,'existingMaintenanceRole':user,
            'originalHbaSHA256':hashlib.sha256(original).hexdigest(),'originalHbaPath':str(original_path),'runtimeStopIssued':False})
        patched=original+b'\n# temporary owned-lab physical backup only\nlocal replication '+user.encode()+b' trust\n'
        def put(data):
            proc=subprocess.run(['docker','--context',CONTEXT,'exec','-i',name,'sh','-c','cat > "$1"','sh',hba],input=data,capture_output=True)
            assert proc.returncode==0
            assert psql(name,user,'SELECT pg_reload_conf()')=='t'
        success=False
        try:
            put(patched)
            fd=os.open(archive,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(fd,'wb') as f:
                proc=subprocess.run(['docker','--context',CONTEXT,'exec',name,'pg_basebackup','-U',user,'-D','-','-Ft','-X','fetch','--checkpoint=fast','--manifest-checksums=SHA256'],stdout=f,stderr=subprocess.PIPE)
            (OUT/(name+'-backup-r2.log')).write_bytes(proc.stderr)
            assert proc.returncode==0, 'Backup failed: source HBA restored; keep VM running'
            with tarfile.open(archive,'r:') as tar:
                names={m.name.lstrip('./') for m in tar}
            assert {'PG_VERSION','global/pg_control','backup_label','backup_manifest'}<=names
            assert any(n.startswith('pg_wal/') and len(n.split('/')[-1])==24 for n in names)
            success=True
        finally:
            put(original)
            assert run(name,'cat',hba,capture_output=True).stdout==original
            save(name+'-hba-restored.json',{'originalHbaSHA256':hashlib.sha256(original).hexdigest(),'exactRestored':True,'reloadVerified':True})
        assert success
        save(name+'-backup.json',{'container':name,'containerId':cid,'cluster':metadata['cluster'],'databases':metadata['databases'],
            'archivePath':str(archive),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'bytes':archive.stat().st_size,
            'physicalControlAndWalIncluded':True,'originalHbaRestored':True,'overrideOriginalHbaBeforeRestoredStartup':True,
            'restoreVerified':False})
        print(json.dumps({'container':name,'physicalBackupSaved':True,'originalHbaRestored':True}),flush=True)
