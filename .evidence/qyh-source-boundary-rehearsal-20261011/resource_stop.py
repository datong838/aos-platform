"""Release only the fully archived owned Source lab after bound material review."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import resource_checkpoint as C


if __name__=='__main__':
    m=json.loads((C.OUT/'manifest.json').read_text())
    assert m['container']==C.CID and m['owner']==C.OWNER and m['task']==C.TASK
    assert m['allArchivesFullyDecoded'] and m['beforeAfterFingerprintsEqual']
    assert m['rolesAndMembershipsUnchanged'] and m['labStopped'] is False
    assert m['repo']==str(C.ROOT)
    a=json.loads((C.CTX/'authority.json').read_text())
    assert a['project_revision']==m['authorityRevision']
    t=json.loads((C.CTX/'receipts/tasks'/f'{C.TASK}.json').read_text())
    leases=json.loads((C.CTX/'leases.json').read_text())['leases']
    assert t in leases and t['owner']==C.OWNER and t['base_revision']==m['taskBaseRevision']
    assert datetime.fromisoformat(t['lease_expires_at'])>datetime.now(timezone.utc)
    review=C.ROOT/'.evidence/qyh-source-resource-checkpoint-review-20261013'
    consumed=json.loads((review/'consumption-r3.json').read_text())
    assert consumed['status']=='CONSUMED_MATERIAL_REVIEW' and consumed['execution_authorized'] is False
    request=json.loads((review/'request-r3.json').read_text())
    frozen=request['materials']['.evidence/qyh-source-resource-checkpoint-review-20261013/material-2.txt']
    assert frozen==(C.OUT/'manifest.json').read_text()
    for name,digest in m['files'].items():
        for suffix in ('','.second'):
            assert hashlib.sha256((C.OUT/'private'/(name+suffix)).read_bytes()).hexdigest()==digest
    for name,digest in m['configurationFilesRetainedHashes'].items():
        assert hashlib.sha256((C.ROOT/name).read_bytes()).hexdigest()==digest
    saved=json.loads((C.OUT/'private/metadata.json').read_text())
    assert C.metadata()==saved and saved['otherClients']==0
    # O_EXCL intent prevents a second stop or unknown-effect replay.
    C.record('stop-intent.json',{'container':C.CID,'manifestSHA256':hashlib.sha256(frozen.encode()).hexdigest(),
        'reviewConsumed':True,'currentDatabaseTouched':False,'tmpfsDataRecoverableOnlyFromArchives':True})
    C.docker('stop','--time','10',C.CID,capture_output=True,text=True)
    state=json.loads(C.docker('inspect',C.CID,capture_output=True,text=True).stdout)[0]
    assert state['Id']==C.CID and not state['State']['Running']
    for name,digest in m['files'].items():
        assert hashlib.sha256((C.OUT/'private'/name).read_bytes()).hexdigest()==digest
        assert hashlib.sha256((C.OUT/'private'/(name+'.second')).read_bytes()).hexdigest()==digest
    memory=C.docker('exec','qyh-restored-pg-20261011','cat','/proc/meminfo',capture_output=True,text=True).stdout
    available=int(next(x for x in memory.splitlines() if x.startswith('MemAvailable:')).split()[1])
    C.record('stop-terminal.json',{'outcome':'ARCHIVED_SOURCE_LAB_PROCESS_STOPPED_BACKUPS_RETAINED',
        'container':C.CID,'containerDeleted':False,'databaseArchives':m['databaseCount'],
        'allBackupHashesValid':True,'measuredVmAvailableKB':available,'currentServicesRestarted':False,
        'fullRestoreRehearsalAccepted':False,'sourceTaskCompleted':False,'goalUpdated':False})
    print('ARCHIVED_SOURCE_LAB_PROCESS_STOPPED_BACKUPS_RETAINED',available)
