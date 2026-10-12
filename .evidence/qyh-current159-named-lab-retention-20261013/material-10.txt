"""Preserve the completed owned lab's volume and archives; stop its exact CID."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

OUT = Path(__file__).resolve().parent
CONTEXT = 'colima-aos-extension'
CID = '52cc28f30197cc4010bd0167139e849e239591d7d9c47023ebcb36ac06164e7c'
VOLUME = 'aos-qyh-source161-clean-maintenance-data-20261012'
OWNER = 'codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2'
RECEIPTS = OUT.parents[2]/'docs/palantier/AOS项目开发上下文/memory/receipts'


def record(name, value):
    with (OUT/name).open('x') as file:
        json.dump(value,file,ensure_ascii=False,indent=2)


def docker(*args, **kwargs):
    return subprocess.run(['docker','--context',CONTEXT,*args],
                          check=True,timeout=60,**kwargs)


def catalog():
    query = """BEGIN READ ONLY; SELECT json_build_object(
        'cluster',(SELECT system_identifier::text FROM pg_control_system()),
        'databases',(SELECT json_agg(datname ORDER BY datname) FROM pg_database WHERE NOT datistemplate),
        'otherClients',(SELECT count(*) FROM pg_stat_activity WHERE pid<>pg_backend_pid()
            AND backend_type='client backend')); COMMIT;"""
    return json.loads(docker('exec','-i',CID,'psql','-X','-qAt','-v','ON_ERROR_STOP=1',
        '-U','aos_app','-d','postgres',input=query,text=True,capture_output=True).stdout)


if __name__ == '__main__':
    task = json.loads((RECEIPTS/'tasks/qyh-source161-clean-maintenance-lab-20261012.json').read_text())
    delivery = json.loads((RECEIPTS/'deliveries/qyh-source161-clean-maintenance-lab-20261012.json').read_text())
    assert task['owner']==OWNER and delivery['task_id']==task['task_id']
    assert delivery['completed_at'] and 'aos-platform/maintenance/qiyuehui-source161-clean-maintenance-lab' in task['scope']
    original = json.loads(docker('inspect',CID,capture_output=True,text=True).stdout)[0]
    assert original['Id']==CID and original['State']['Running']
    assert original['Name']=='/qyh-source161-clean-maintenance-lab-20261012'
    assert original['HostConfig']['NetworkMode']=='none' and not original['HostConfig']['PortBindings']
    assert len(original['Mounts'])==1 and original['Mounts'][0]['Name']==VOLUME
    assert original['Mounts'][0]['Type']=='volume'
    before = catalog()
    assert before['cluster']=='7695744911813242913' and before['otherClients']==0
    assert all(re.fullmatch('[a-zA-Z0-9_]+',name) for name in before['databases'])
    record('intent.json',{'owner':OWNER,'completedOriginalTask':task['task_id'],
        'container':CID,'volume':VOLUME,'catalog':before,'sourceDatabaseAffected':False})
    private = OUT/'private'
    private.mkdir(mode=0o700)
    archive_hashes = {}
    commands = [(name+'.dump',['pg_dump','-U','aos_app','-d',name,'-Fc'])
                for name in before['databases']]
    commands.append(('globals.sql',['pg_dumpall','-U','aos_app','--globals-only','--no-role-passwords']))
    for filename,command in commands:
        path = private/filename
        fd = os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'wb') as file:
            docker('exec',CID,*command,stdout=file,stderr=subprocess.PIPE)
        second = private/(filename+'.second')
        shutil.copyfile(path,second)
        second.chmod(0o600)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert hashlib.sha256(second.read_bytes()).hexdigest()==digest
        archive_hashes[filename]=digest
        if filename.endswith('.dump'):
            docker('exec','-i',CID,'pg_restore','--list',input=path.read_bytes(),
                   stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    assert catalog()==before
    record('backup-terminal.json',{'completeDatabaseArchives':len(before['databases']),
        'secondCopiesEqual':True,'archiveListReadable':True,'catalogUnchanged':True,
        'files':archive_hashes,'volumeRetained':True})
    record('stop-intent.json',{'container':CID,'volume':VOLUME,'removeVolume':False,
        'completedOwner':OWNER,'activeClients':0})
    docker('stop','--time','10',CID,capture_output=True,text=True)
    stopped = json.loads(docker('inspect',CID,capture_output=True,text=True).stdout)[0]
    retained = json.loads(docker('volume','inspect',VOLUME,capture_output=True,text=True).stdout)[0]
    assert not stopped['State']['Running'] and stopped['Id']==CID
    assert retained['Name']==VOLUME and stopped['Mounts'][0]['Name']==VOLUME
    for name,digest in archive_hashes.items():
        assert hashlib.sha256((private/name).read_bytes()).hexdigest()==digest
        assert hashlib.sha256((private/(name+'.second')).read_bytes()).hexdigest()==digest
    memory = docker('exec','qyh-restored-pg-20261011','cat','/proc/meminfo',
                    capture_output=True,text=True).stdout
    available = int(next(line for line in memory.splitlines() if line.startswith('MemAvailable:')).split()[1])
    record('verification.json',{'outcome':'COMPLETED_OWNED_NAMED_LAB_STOPPED_DATA_RETAINED',
        'container':CID,'volume':VOLUME,'volumeStillExists':True,'allBackupHashesValid':True,
        'databaseArchives':len(before['databases']),'measuredVmAvailableKB':available,
        'otherContainersStopped':False,'currentServicesRestarted':False,
        'fullRestoreRehearsalPassed':False,'goalUpdated':False})
    print('COMPLETED_OWNED_NAMED_LAB_STOPPED_DATA_RETAINED',available)
