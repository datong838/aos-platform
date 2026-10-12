"""Physical preservation before a runtime restart; no container stop or rebuild."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile

OUT=Path(__file__).parent
CONTEXT='colima-aos-extension'


def write(name,value):
    with (OUT/name).open('x') as f:json.dump(value,f,indent=2)


def inspect(name):
    fmt='{"Id":{{json .Id}},"Image":{{json .Image}},"Tmpfs":{{json (index .HostConfig "Tmpfs")}},"Mounts":{{json .Mounts}},"RestartPolicy":{{json .HostConfig.RestartPolicy}},"Running":{{json .State.Running}}}'
    return json.loads(subprocess.check_output(['docker','--context',CONTEXT,'inspect','--format',fmt,name],text=True))


if __name__=='__main__':
    private=OUT/'private';private.mkdir(mode=0o700,exist_ok=True)
    inventory=OUT/'before-containers.json'
    if inventory.exists():
        before=json.loads(inventory.read_text())
    else:
        names=subprocess.check_output(['docker','--context',CONTEXT,'ps','--format','{{.Names}}'],text=True).splitlines()
        before={name:inspect(name) for name in names}
        assert all(name.startswith(('qyh-','aos-qyh-','aos-a0v-recovery-pg')) for name in names)
        write('before-containers.json',before)
    results=[]
    for name,resource in before.items():
        if not resource['Tmpfs']:continue
        live=inspect(name);assert live['Id']==resource['Id'] and live['Running']
        result_path=OUT/(name+'-backup.json')
        archive=private/(name+'.tar')
        if result_path.exists():
            result=json.loads(result_path.read_text())
            assert result['sha256']==hashlib.sha256(archive.read_bytes()).hexdigest()
            results.append(result);continue
        intent=OUT/(name+'-intent.json')
        assert not intent.exists(), 'Unknown/failed attempt: reconcile before backup retry'
        bootstrap=subprocess.check_output(['docker','--context',CONTEXT,'exec',name,'printenv','POSTGRES_USER'],text=True).strip()
        assert bootstrap and all(c.isalnum() or c=='_' for c in bootstrap)
        metadata=json.loads(subprocess.check_output(['docker','--context',CONTEXT,'exec',name,'psql','-X','-qAt','-U',bootstrap,'-d','postgres','-c',
            "BEGIN READ ONLY; SELECT json_build_object('cluster',(SELECT system_identifier::text FROM pg_control_system()),'databases',(SELECT json_agg(datname ORDER BY datname) FROM pg_database WHERE NOT datistemplate)); COMMIT;"],text=True))
        write(name+'-intent.json',{'containerId':live['Id'],'metadata':metadata,'existingMaintenanceRole':bootstrap,'archivePath':str(archive),'stopIssued':False})
        fd=os.open(archive,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'wb') as f:
            proc=subprocess.run(['docker','--context',CONTEXT,'exec',name,'pg_basebackup','-U',bootstrap,'-D','-','-Ft','-X','fetch','--checkpoint=fast'],stdout=f,stderr=subprocess.PIPE)
        (OUT/(name+'-backup.log')).write_bytes(proc.stderr)
        assert proc.returncode==0, 'Physical backup failed; VM must remain running'
        with tarfile.open(archive,'r:') as tar:
            names={m.name.lstrip('./') for m in tar}
        assert {'PG_VERSION','global/pg_control','backup_label'}<=names
        assert any(n.startswith('pg_wal/') and len(n.split('/')[-1])==24 for n in names)
        result={'container':name,'containerId':live['Id'],'cluster':metadata['cluster'],'databases':metadata['databases'],
                'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'bytes':archive.stat().st_size,
                'physicalControlAndWalIncluded':True,'privateMode':'0600','restoreVerified':False}
        write(name+'-backup.json',result);results.append(result)
        print(json.dumps({'container':name,'physicalBackupSaved':True,'bytes':result['bytes']}),flush=True)
    assert len(results)==7
    write('tmpfs-preservation-summary.json',{'physicalBackups':results,'sevenArchivesSaved':True,'allRestoresVerified':False,'runtimeStopIssued':False})
