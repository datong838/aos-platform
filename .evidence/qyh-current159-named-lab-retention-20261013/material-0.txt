"""Archive two exact historical named labs; keep volumes, source and failed data."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
OLD=ROOT/'.evidence/qyh-current159-fresh-backup-restore-20261012'
spec=importlib.util.spec_from_file_location('retention_helpers',ROOT /
    '.evidence/qyh-completed-named-lab-resource-retention-20261013/retain.py')
R=importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
LABS=[('exact','qyh-current159-exact-restore-20261012','exact-lab-created.json'),
      ('failed-retained','qyh-current159-restore-lab-20261012','lab-created.json')]


if __name__=='__main__':
    task=json.loads((R.RECEIPTS/'tasks/qyh-current159-fresh-backup-restore-20261012.json').read_text())
    delivery=json.loads((R.RECEIPTS/'deliveries/qyh-current159-fresh-backup-restore-20261012.json').read_text())
    assert task['owner']=='codex-thread-01a107a2-e9e4-7670-bc44-1144fa9b27e2'
    assert delivery['task_id']==task['task_id'] and delivery['completed_at']
    assert 'aos-platform/maintenance/qyh-current159-owned-restore' in task['scope']
    results=[]
    for label,name,proof in LABS:
        original=json.loads((OLD/proof).read_text())
        R.CID=original['containerId'];R.VOLUME=original['volume'];R.OUT=OUT/label
        R.OUT.mkdir()
        native=json.loads(R.docker('inspect',R.CID,capture_output=True,text=True).stdout)[0]
        assert native['Id']==R.CID and native['Name']=='/'+name and native['State']['Running']
        assert native['HostConfig']['NetworkMode']=='none' and not native['HostConfig']['PortBindings']
        assert len(native['Mounts'])==1 and native['Mounts'][0]['Type']=='volume'
        assert native['Mounts'][0]['Name']==R.VOLUME
        before=R.catalog()
        assert before['otherClients']==0 and before['cluster']
        assert all(re.fullmatch('[a-zA-Z0-9_]+',db) for db in before['databases'])
        R.record('intent.json',{'originalOwner':task['owner'],'originalTask':task['task_id'],
            'container':R.CID,'volume':R.VOLUME,'catalog':before,'failedOriginalLab':label=='failed-retained'})
        private=R.OUT/'private';private.mkdir(mode=0o700)
        commands=[(db+'.dump',['pg_dump','-U','aos_app','-d',db,'-Fc']) for db in before['databases']]
        commands.append(('globals.sql',['pg_dumpall','-U','aos_app','--globals-only','--no-role-passwords']))
        checks={}
        for filename,args in commands:
            p=private/filename
            with os.fdopen(os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'wb') as f:
                R.docker('exec',R.CID,*args,stdout=f,stderr=subprocess.PIPE)
            second=private/(filename+'.second');shutil.copyfile(p,second);second.chmod(0o600)
            digest=hashlib.sha256(p.read_bytes()).hexdigest()
            assert hashlib.sha256(second.read_bytes()).hexdigest()==digest
            checks[filename]=digest
            if filename.endswith('.dump'):
                R.docker('exec','-i',R.CID,'pg_restore','--list',input=p.read_bytes(),
                         stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        assert R.catalog()==before
        R.record('backup-terminal.json',{'archiveCount':len(before['databases']),
            'files':checks,'secondCopiesEqual':True,'archiveListsReadable':True,'catalogUnchanged':True})
        R.record('stop-intent.json',{'container':R.CID,'volume':R.VOLUME,'removeVolume':False})
        R.docker('stop','--time','10',R.CID,capture_output=True,text=True)
        stopped=json.loads(R.docker('inspect',R.CID,capture_output=True,text=True).stdout)[0]
        volume=json.loads(R.docker('volume','inspect',R.VOLUME,capture_output=True,text=True).stdout)[0]
        assert not stopped['State']['Running'] and volume['Name']==R.VOLUME
        for filename,digest in checks.items():
            assert hashlib.sha256((private/filename).read_bytes()).hexdigest()==digest
            assert hashlib.sha256((private/(filename+'.second')).read_bytes()).hexdigest()==digest
        result={'container':R.CID,'originalVolumeRetained':R.VOLUME,'stopped':True,
            'completeArchives':len(before['databases']),'backupHashesValid':True,
            'failedLabPreservedNotAccepted':label=='failed-retained'}
        R.record('verification.json',result);results.append(result)
    R.OUT=OUT
    memory=R.docker('exec','qyh-restored-pg-20261011','cat','/proc/meminfo',capture_output=True,text=True).stdout
    available=int(next(x for x in memory.splitlines() if x.startswith('MemAvailable:')).split()[1])
    R.record('verification.json',{'outcome':'TWO_OWNED_CURRENT159_NAMED_LABS_ARCHIVED_STOPPED',
        'resources':results,'measuredVmAvailableKB':available,'currentDatabaseTouched':False,
        'currentServicesRestarted':False,'fullRestoreRehearsalAccepted':False,'goalUpdated':False})
    print('TWO_OWNED_CURRENT159_NAMED_LABS_ARCHIVED_STOPPED',available)
