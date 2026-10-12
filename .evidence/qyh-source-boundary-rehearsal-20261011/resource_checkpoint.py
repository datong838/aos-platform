"""Archive an exact owned tmpfs lab; never stops it or writes any database."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import argparse

OUT=Path(__file__).resolve().parent/'resource-checkpoint-20261013'
ROOT=OUT.parents[2]
CONTEXT='colima-aos-extension'
CID='bb9c8b1ab46af632af36ee89c9f2686f06ace9bbd803040ce44cab057968d486'
TASK='qyh-source-boundary-rehearsal-20261011'
OWNER='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2'
CTX=ROOT.parent/'docs/palantier/AOS项目开发上下文/memory'


def record(name,value):
    with (OUT/name).open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2)


def docker(*args,**kwargs):
    return subprocess.run(['docker','--context',CONTEXT,*args],check=True,timeout=90,**kwargs)


def query(db,statement):
    return docker('exec','-i',CID,'psql','-X','-qAt','-v','ON_ERROR_STOP=1',
        '-U','aos_app','-d',db,input=statement,text=True,capture_output=True).stdout


def metadata():
    return json.loads(query('postgres',"""BEGIN READ ONLY; SELECT json_build_object(
      'cluster',(SELECT system_identifier::text FROM pg_control_system()),
      'databases',(SELECT json_agg(json_build_object('name',datname,'owner',pg_get_userbyid(datdba)) ORDER BY datname) FROM pg_database WHERE NOT datistemplate),
      'otherClients',(SELECT count(*) FROM pg_stat_activity WHERE pid<>pg_backend_pid() AND backend_type='client backend'),
      'storedLoginCredentials',(SELECT count(*) FROM pg_authid WHERE rolcanlogin AND rolpassword IS NOT NULL),
      'bootstrap',(SELECT rolname FROM pg_roles WHERE oid=10),
      'roles',(SELECT json_agg(row_to_json(x)) FROM (SELECT rolname,rolsuper,rolinherit,rolcreaterole,rolcreatedb,rolcanlogin,rolreplication,rolbypassrls,rolconnlimit,rolconfig FROM pg_roles ORDER BY rolname)x),
      'memberships',(SELECT json_agg(row_to_json(x)) FROM (SELECT pg_get_userbyid(roleid) AS role,pg_get_userbyid(member) AS member,pg_get_userbyid(grantor) AS grantor,admin_option,inherit_option,set_option FROM pg_auth_members ORDER BY roleid,member)x)); COMMIT;"""))


def fingerprints(db):
    inventory="SELECT coalesce(json_agg(json_build_object('schema',n.nspname,'name',c.relname) ORDER BY n.nspname,c.relname),'[]'::json) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='r' AND n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%';"
    tables=json.loads(query(db,'BEGIN READ ONLY; '+inventory+' COMMIT;')) or []
    statements=['BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;',"SET LOCAL work_mem='1MB';",
                'SET LOCAL max_parallel_workers_per_gather=0;',"SET LOCAL statement_timeout='5s';",inventory]
    for t in tables:
        qualified='.'.join('"'+t[k].replace('"','""')+'"' for k in ('schema','name'))
        key=(t['schema']+'.'+t['name']).replace("'","''")
        statements.append("SELECT row_to_json(x) FROM (SELECT '"+key+"' AS name,count(*) AS rows,encode(sha256(convert_to(coalesce(string_agg(h,'' ORDER BY h),''),'UTF8')),'hex') AS hash FROM (SELECT encode(sha256(convert_to(to_jsonb(t)::text,'UTF8')),'hex') AS h FROM "+qualified+" t)q)x;")
    # Sequence current values are retained in the native archive; hash their
    # independent readback as additional recovery metadata without advancing them.
    statements.append("SELECT coalesce(json_agg(row_to_json(x)),'[]'::json) FROM (SELECT schemaname,sequencename,sequenceowner,data_type::text,start_value,min_value,max_value,increment_by,cycle,cache_size,last_value FROM pg_sequences WHERE schemaname NOT IN ('pg_catalog','information_schema') ORDER BY schemaname,sequencename)x;")
    statements.append('COMMIT;')
    result=query(db,'\n'.join(statements))
    rows=[json.loads(x) for x in result.splitlines() if x.strip()]
    assert (rows[0] or [])==tables and len(rows)==len(tables)+2
    values={x['name']:{'rows':x['rows'],'hash':x['hash']} for x in rows[1:-1]}
    assert len(values)==len(tables)
    return {'tables':values,'sequences':rows[-1] or []}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--resume-after-empty-catalog',action='store_true')
    resume=parser.parse_args().resume_after_empty_catalog
    authority=json.loads((CTX/'authority.json').read_text())
    task=json.loads((CTX/'receipts/tasks'/f'{TASK}.json').read_text())
    leases=json.loads((CTX/'leases.json').read_text())['leases']
    assert task in leases and task['owner']==OWNER
    assert datetime.fromisoformat(task['lease_expires_at'])>datetime.now(timezone.utc)
    assert 'aos-platform/maintenance/qiyuehui-source-boundary-clone' in task['scope']
    native=json.loads(docker('inspect',CID,capture_output=True,text=True).stdout)[0]
    assert native['Id']==CID and native['State']['Running'] and not native['Mounts']
    assert native['Name']=='/qyh-source-boundary-clone-capacity-20261012'
    assert native['NetworkSettings']['Ports']['5432/tcp']==[{'HostIp':'127.0.0.1','HostPort':'18431'}]
    initial=metadata()
    assert initial['cluster']=='7695416748450308141' and initial['otherClients']==0
    assert initial['storedLoginCredentials']==0 and initial['bootstrap']=='aos_app'
    assert len(initial['databases'])==5
    memory=docker('exec',CID,'cat','/proc/meminfo',capture_output=True,text=True).stdout
    available=int(next(x for x in memory.splitlines() if x.startswith('MemAvailable:')).split()[1])
    assert available>=256*1024
    if resume:
        intent=json.loads((OUT/'intent.json').read_text())
        assert intent['container']==CID and intent['owner']==OWNER and intent['cluster']==initial['cluster']
        assert {x.name for x in OUT.iterdir() if x.is_file()}=={'intent.json','aos_meta_head-terminal.json'}
        assert {x.name for x in (OUT/'private').iterdir()}=={'aos_meta_head.dump','aos_meta_head.dump.second'}
    else:
        OUT.mkdir()
        record('intent.json',{'task':TASK,'owner':OWNER,'authorityRevision':authority['project_revision'],
            'container':CID,'cluster':initial['cluster'],'memoryAvailableKB':available,
            'writesOrStopAuthorizedByThisScript':False})
    private=OUT/'private'
    if not resume:private.mkdir(mode=0o700)
    hashes={};snapshots={};configuration_hashes={}
    for p in (OUT.parent/'private').rglob('*'):
        if p.is_file() and not p.is_symlink():
            configuration_hashes[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    for item in initial['databases']:
        db=item['name'];assert re.fullmatch('[a-zA-Z0-9_]+',db)
        before=fingerprints(db)
        p=private/(db+'.dump')
        if resume and db=='aos_meta_head':
            terminal=json.loads((OUT/'aos_meta_head-terminal.json').read_text())
            digest=hashlib.sha256(p.read_bytes()).hexdigest()
            assert digest==terminal['sha256']==hashlib.sha256((private/'aos_meta_head.dump.second').read_bytes()).hexdigest()
            assert terminal['entireArchiveDecodedWithoutExecution'] and terminal['tablesAndSequencesUnchanged']
            assert terminal['tables']==len(before['tables'])
            hashes[p.name]=digest;snapshots[db]=before
            continue  # Already known terminal: never re-export or overwrite it.
        with os.fdopen(os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'wb') as f:
            docker('exec',CID,'pg_dump','-U','aos_app','-d',db,'-Fc',stdout=f,stderr=subprocess.PIPE)
        second=private/(db+'.dump.second');shutil.copyfile(p,second);second.chmod(0o600)
        digest=hashlib.sha256(p.read_bytes()).hexdigest()
        assert hashlib.sha256(second.read_bytes()).hexdigest()==digest
        for options in [('--list',),('--file=/dev/null',)]:
            docker('exec','-i',CID,'pg_restore',*options,input=p.read_bytes(),
                   stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        assert fingerprints(db)==before
        snapshots[db]=before;hashes[p.name]=digest
        record(db+'-terminal.json',{'tables':len(before['tables']),'sha256':digest,
            'secondCopyEqual':True,'entireArchiveDecodedWithoutExecution':True,
            'tablesAndSequencesUnchanged':True})
    p=private/'globals.sql'
    with os.fdopen(os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'wb') as f:
        docker('exec',CID,'pg_dumpall','-U','aos_app','--globals-only','--no-role-passwords',
               stdout=f,stderr=subprocess.PIPE)
    second=private/'globals.sql.second';shutil.copyfile(p,second);second.chmod(0o600)
    digest=hashlib.sha256(p.read_bytes()).hexdigest();assert hashlib.sha256(second.read_bytes()).hexdigest()==digest
    hashes[p.name]=digest
    assert metadata()==initial
    for path,digest in configuration_hashes.items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest
    record('snapshots.json',snapshots)
    # Role config is retained privately, never passed as model material.
    with (private/'metadata.json').open('x') as f:
        os.chmod(f.name,0o600);json.dump(initial,f,ensure_ascii=False,indent=2)
    record('manifest.json',{'schema':'qyh-source-lab-recovery-checkpoint/v1','task':TASK,
        'thread':'01a107a2-e9e4-7670-bc44-1144fa9b27e2','owner':OWNER,'repo':str(ROOT),
        'authorityRevision':authority['project_revision'],'taskBaseRevision':task['base_revision'],
        'container':CID,'cluster':initial['cluster'],'databaseCount':5,'files':hashes,
        'configurationFilesRetainedHashes':configuration_hashes,'bootstrap':'aos_app',
        'nativeOwnerACLSequenceArchives':True,'allArchivesFullyDecoded':True,
        'beforeAfterFingerprintsEqual':True,'rolesAndMembershipsUnchanged':True,
        'labStopped':False,'fullRestoreRehearsalPassed':False,'currentDatabaseTouched':False,
        'limitations':['Archive decoding is not an actual restore. Before future formal use, restore to independent owned lab, compare full hashes and handle role OID drift by original maintenance contract.']})
    print('FIVE_DATABASE_SOURCE_LAB_RECOVERY_ARCHIVES_VERIFIED_NOT_STOPPED')
