"""One-shot complete current QYH backup/restore; never mutates source DB."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/aos-api'))
sys.path.insert(0,str(ROOT/'.evidence/qyh-full-system-restoration-20261011'))
import promote_stage_transport as S

R=Path(__file__).resolve().parent
PRIVATE=R/'private'
TARGET='qyh-source-boundary-clone-20261011'
PORT=18431


def record(name,value):
    with (R/name).open('x') as f:
        json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')


def command(args,*,data=None,output=None):
    result=subprocess.run(S.DOCKER+args,input=data,stdout=output or subprocess.PIPE,
        stderr=subprocess.PIPE,timeout=180)
    if result.returncode:
        # Server errors may contain sensitive restored data; retain privately only.
        with (PRIVATE/('failure-'+str(time.time_ns())+'.log')).open('xb') as f:
            os.chmod(f.name,0o600);f.write(result.stderr)
        raise RuntimeError('Clone operation failed; reconcile private evidence; do not replay')
    return result.stdout


def metadata(container):
    return S.D.metadata(container)


if __name__=='__main__':
    assert not (R/'backup-intent.json').exists(),'Existing intent: reconcile, never replay'
    assert subprocess.run(S.DOCKER+['inspect',TARGET],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0
    with socket.socket() as probe:assert probe.connect_ex(('127.0.0.1',PORT))!=0,'Occupied port; no takeover'
    source=json.loads(command(['inspect','--format','{"Id":{{json .Id}},"Image":{{json .Image}},"Mounts":{{json .Mounts}}}',S.SOURCE]))
    assert source['Id']=='84989681fb7d3fc0f42d750672547ca0208fbba08dfef0d93837d8e64245dc3c'
    assert source['Image']==S.P.M.IMAGE and any(m.get('Name')==S.P.VOLUME for m in source['Mounts'])
    identity=S.P.native_identity(S.SOURCE)
    assert identity['cluster']==S.P.CLUSTER and identity['schema']=='a0v_159' and identity['disabledBindings'] is True
    before=S.P.M.fingerprint(S.SOURCE);assert len(before)==647
    old_metadata=metadata(S.SOURCE)
    PRIVATE.mkdir(mode=0o700)
    record('backup-intent.json',{'source':source,'identity':identity,'sourceWrites':False})
    files={}
    for name,args in [('current.dump',['pg_dump','-U','aos_app','-d','aos_meta_head','-Fc']),('globals.sql',['pg_dumpall','-U','aos_app','--globals-only','--no-role-passwords'])]:
        path=PRIVATE/name
        with path.open('xb') as stream:
            os.chmod(path,0o600);command(['exec',S.SOURCE]+args,output=stream)
        copy=PRIVATE/(name+'.second-copy');shutil.copyfile(path,copy);copy.chmod(0o600)
        digest=hashlib.sha256(path.read_bytes()).hexdigest();assert hashlib.sha256(copy.read_bytes()).hexdigest()==digest
        files[name]={'sha256':digest,'bytes':path.stat().st_size,'secondCopyExact':True}
    assert S.P.M.fingerprint(S.SOURCE)==before and metadata(S.SOURCE)==old_metadata
    record('backup-verified.json',{'tables':647,'files':files,'rolePasswordsIncluded':False,'secondIndependentSnapshot':False})
    record('create-intent.json',{'target':TARGET,'port':PORT,'image':S.P.M.IMAGE,'storage':'tmpfs512m','sourceVolumeAttached':False})
    cid=command(['run','--detach','--name',TARGET,'--label','aos.task=qyh-source-boundary-clone-20261011',
        '--publish',f'127.0.0.1:{PORT}:5432','--tmpfs','/var/lib/postgresql/data:rw,nosuid,size=512m',
        '-e','POSTGRES_USER=aos_app','-e','POSTGRES_DB=postgres','-e','POSTGRES_HOST_AUTH_METHOD=trust',S.P.M.IMAGE]).decode().strip()
    record('created.json',{'containerId':cid,'target':TARGET})
    for _ in range(40):
        ready=subprocess.run(S.DOCKER+['exec',TARGET,'pg_isready','-U','aos_app'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        main=subprocess.run(S.DOCKER+['exec',TARGET,'cat','/proc/1/comm'],capture_output=True)
        if ready.returncode==0 and main.stdout.strip()==b'postgres':break
        time.sleep(.25)
    else:raise RuntimeError('Clone readiness unknown; reconcile existing target')
    record('restore-intent.json',{'target':TARGET,'backupHashes':files,'restoreAllOwnersAndAcls':True})
    globals_data=(PRIVATE/'globals.sql').read_text()
    assert globals_data.splitlines().count('CREATE ROLE aos_app;')==1
    globals_data='\n'.join(line for line in globals_data.splitlines() if line!='CREATE ROLE aos_app;')+'\n'
    command(['exec','-i',TARGET,'psql','-X','-q','-v','ON_ERROR_STOP=1','-U','aos_app','-d','postgres'],data=globals_data.encode())
    command(['exec',TARGET,'psql','-X','-q','-v','ON_ERROR_STOP=1','-U','aos_app','-d','postgres','-c','CREATE DATABASE aos_meta_head OWNER aos_app'])
    command(['cp',str(PRIVATE/'current.dump'),TARGET+':/tmp/current.dump'])
    command(['exec',TARGET,'pg_restore','--exit-on-error','-U','aos_app','-d','aos_meta_head','/tmp/current.dump'])
    restored=S.P.M.fingerprint(TARGET);assert restored==before
    restored_metadata=metadata(TARGET);assert restored_metadata==old_metadata
    assert S.P.M.fingerprint(S.SOURCE)==before and metadata(S.SOURCE)==old_metadata
    observed=S.P.native_identity(TARGET);assert observed['cluster']!=identity['cluster'] and observed['schema']==identity['schema']
    item=json.loads(command(['inspect','--format','{"Id":{{json .Id}},"Image":{{json .Image}},"Mounts":{{json .Mounts}},"Ports":{{json .NetworkSettings.Ports}}}',TARGET]))
    assert item['Id']==cid and item['Mounts']==[] and item['Ports']=={'5432/tcp':[{'HostIp':'127.0.0.1','HostPort':str(PORT)}]}
    record('restore-verified.json',{'tables':647,'sourceAndCloneDataExact':True,'allMetadataExact':{k:len(v) for k,v in old_metadata.items()},
        'sourceUnchanged':True,'cloneIdentity':observed,'container':item,'credentialsAuthenticated':False,'sourceBoundaryAccepted':False,'fullGoalAccepted':False})
    print('CURRENT647_COMPLETE_PERMISSION_FAITHFUL_CLONE_VERIFIED')
