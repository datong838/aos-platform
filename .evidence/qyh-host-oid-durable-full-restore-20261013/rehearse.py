"""Fresh bounded durable-volume rehearsal; source is always read-only."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from datetime import datetime, timezone

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
NAME=OUT.name
SOURCE='qyh-restored-pg-20261011'
CID='84989681fb7d3fc0f42d750672547ca0208fbba08dfef0d93837d8e64245dc3c'
IMAGE='sha256:7e7dbab8d3b431a20793a6d99cb5a6bc84e44914309917f1bf5589a7568cdefd'
CONTEXT='colima-aos-extension'
DB='qyh_oid_full_restore'
OWNER='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2'

def record(name,value):
    with (OUT/name).open('x') as f:json.dump(value,f,indent=2)

def docker(*args,**kw):
    return subprocess.run(['docker','--context',CONTEXT,*args],check=True,timeout=180,**kw)

def sql(container,db,query):
    return docker('exec','-i',container,'psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','aos_app','-d',db,input=query,text=True,capture_output=True).stdout

INVENTORY="SELECT coalesce(json_agg(json_build_object('schema',n.nspname,'name',c.relname) ORDER BY n.nspname,c.relname),'[]') FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='r' AND n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%';"

def fingerprint(container,db):
    tables=json.loads(sql(container,db,'BEGIN READ ONLY;'+INVENTORY+'COMMIT;'))
    assert len(tables)==650
    queries=['BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;',"SET LOCAL work_mem='1MB';",'SET LOCAL max_parallel_workers_per_gather=0;',"SET LOCAL statement_timeout='5s';",INVENTORY]
    for t in tables:
        qualified='.'.join('"'+t[k].replace('"','""')+'"' for k in ('schema','name'))
        key=(t['schema']+'.'+t['name']).replace("'","''")
        queries.append("SELECT row_to_json(x) FROM (SELECT '"+key+"' AS name,count(*) AS rows,encode(sha256(convert_to(coalesce(string_agg(h,'' ORDER BY h),''),'UTF8')),'hex') AS hash FROM (SELECT encode(sha256(convert_to(to_jsonb(t)::text,'UTF8')),'hex') AS h FROM "+qualified+" t) q)x;")
    queries.append('COMMIT;')
    result=sql(container,db,'\n'.join(queries));lines=[json.loads(x) for x in result.splitlines() if x.strip()]
    assert lines[0]==tables and len(lines)==651
    return {r['name']:{'rows':r['rows'],'hash':r['hash']} for r in lines[1:]}

def metadata(container,db):
    roles=json.loads(sql(container,db,"BEGIN READ ONLY;SELECT json_build_object('roles',(SELECT json_agg(row_to_json(x) ORDER BY rolname) FROM (SELECT rolname,rolsuper,rolinherit,rolcreaterole,rolcreatedb,rolcanlogin,rolreplication,rolconnlimit,rolvaliduntil,rolbypassrls,rolconfig FROM pg_roles)x),'members',(SELECT json_agg(row_to_json(x) ORDER BY role,member,grantor) FROM (SELECT r.rolname AS role,m.rolname AS member,g.rolname AS grantor,a.admin_option,a.inherit_option,a.set_option FROM pg_auth_members a JOIN pg_roles r ON r.oid=a.roleid JOIN pg_roles m ON m.oid=a.member JOIN pg_roles g ON g.oid=a.grantor)x));COMMIT;"))
    seqs=json.loads(sql(container,db,"BEGIN READ ONLY;SELECT coalesce(json_agg(row_to_json(x) ORDER BY schemaname,sequencename),'[]') FROM (SELECT schemaname,sequencename,sequenceowner,data_type::text,start_value,min_value,max_value,increment_by,cycle,cache_size,last_value FROM pg_sequences WHERE schemaname NOT LIKE 'pg_%')x;COMMIT;"))
    states={}
    for s in seqs:
        q='.'.join('"'+s[k].replace('"','""')+'"' for k in ('schemaname','sequencename'))
        states[q]=json.loads(sql(container,db,'BEGIN READ ONLY;SELECT row_to_json(x) FROM (SELECT last_value,is_called FROM '+q+')x;COMMIT;'))
    schema=docker('exec',container,'pg_dump','-U','aos_app','-d',db,'--schema-only','--restrict-key=QyhReadonlySchemaComparison20261013',capture_output=True).stdout
    # Database-specific connection directives must not hide schema changes.
    return {'roles':roles,'sequences':seqs,'sequenceStates':states,'schemaSHA256':hashlib.sha256(schema).hexdigest()}

def main():
    spec=importlib.util.spec_from_file_location('mc',ROOT/'scripts/memory/memoryctl.py')
    mc=importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name]=mc;spec.loader.exec_module(mc)
    assert mc.load_authority()['project_revision']=='AOS-001998'
    lease=next(x for x in mc.load_leases(mc.DEFAULT_PATHS)['leases'] if x['task_id']==NAME)
    assert lease['owner']==OWNER and datetime.fromisoformat(lease['lease_expires_at'])>datetime.now(timezone.utc)
    source=json.loads(docker('inspect',SOURCE,text=True,capture_output=True).stdout)[0]
    assert source['Id']==CID and source['State']['Running'] and source['Image']==IMAGE
    assert len(source['Mounts'])==1 and source['Mounts'][0]['Name']=='aos-qyh-history159-prepared-data-20261011'
    mem=docker('exec',SOURCE,'cat','/proc/meminfo',text=True,capture_output=True).stdout
    available=int(next(x for x in mem.splitlines() if x.startswith('MemAvailable:')).split()[1]);assert available>=1048576
    for kind,args in [('container',('ps','-a','--filter','name=^/'+NAME+'$','--format','{{.ID}}')),('volume',('volume','ls','--filter','name=^'+NAME+'$','--format','{{.Name}}'))]:
        r=docker(*args,text=True,capture_output=True);assert not r.stdout.strip() and not r.stderr.strip(),kind+' already exists: reconcile only'
    native=json.loads(sql(SOURCE,'aos_meta_head',"BEGIN READ ONLY;SELECT json_build_object('cluster',(SELECT system_identifier::text FROM pg_control_system()),'schema',(SELECT version_num FROM alembic_version),'enabledBindings',(SELECT count(*) FROM extension_runtime_binding WHERE enabled),'otherTransactions',(SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND state='active' AND xact_start IS NOT NULL));COMMIT;"))
    assert native=={'cluster':'7695302940039200809','schema':'a0v_161','enabledBindings':0,'otherTransactions':0}
    import sys
    resume=sys.argv[1:]==['--resume-after-schema-key']
    private=OUT/'private'
    if resume:
        old=json.loads((OUT/'source-before.json').read_text());failure=json.loads((OUT/'readonly-failure-reconciliation.json').read_text())
        assert failure['changedTables']==[] and failure['changedMetadata']==['schemaSHA256'] and failure['noVolumeCreated'] and failure['noCloneCreated']
        assert set(x.name for x in private.iterdir())=={'current.dump','current.dump.second','globals.sql','globals.sql.second'}
        before=fingerprint(SOURCE,'aos_meta_head');meta=metadata(SOURCE,'aos_meta_head')
        assert before==old['fingerprints']
        assert all(meta[k]==old['metadata'][k] for k in ('roles','sequences','sequenceStates'))
        assert metadata(SOURCE,'aos_meta_head')==meta
        hashes={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in private.iterdir()}
        assert all(hashes[x]==hashes[x+'.second'] for x in ('current.dump','globals.sql'))
        record('resume-schema-key-intent.json',{'reuseCompletedBackups':True,'source650TablesUnchanged':True,'sourceRolesSequencesUnchanged':True,'schemaFixedKeyIndependentReadsEqual':True,'files':hashes})
        record('source-fixed-key-before.json',{'fingerprints':before,'metadata':meta})
    else:
        assert not sys.argv[1:]
        record('intent.json',{'sourceContainer':CID,'sourceVolume':source['Mounts'][0]['Name'],'source':native,'clone':NAME,'memoryAvailableKB':available,'task':NAME,'authority':'AOS-001998','sourceWrites':False})
        before=fingerprint(SOURCE,'aos_meta_head');meta=metadata(SOURCE,'aos_meta_head');record('source-before.json',{'fingerprints':before,'metadata':meta})
        private.mkdir(mode=0o700);hashes={}
        for filename,args in [('current.dump',('pg_dump','-U','aos_app','-d','aos_meta_head','-Fc')),('globals.sql',('pg_dumpall','-U','aos_app','--globals-only','--no-role-passwords'))]:
            p=private/filename
            with os.fdopen(os.open(p,os.O_EXCL|os.O_CREAT|os.O_WRONLY,0o600),'wb') as f:docker('exec',SOURCE,*args,stdout=f,stderr=subprocess.PIPE)
            second=private/(filename+'.second');shutil.copyfile(p,second);second.chmod(0o600)
            for x in (p,second):hashes[x.name]=hashlib.sha256(x.read_bytes()).hexdigest()
            assert hashes[p.name]==hashes[second.name]
    for args in [('--list',),('--file=/dev/null',)]:docker('exec','-i',SOURCE,'pg_restore',*args,input=(private/'current.dump').read_bytes(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    assert fingerprint(SOURCE,'aos_meta_head')==before and metadata(SOURCE,'aos_meta_head')==meta
    record('backup-verified.json',{'files':hashes,'sourceUnchanged':True,'archiveFullyDecoded':True})
    globals_text=(private/'globals.sql').read_text();assert globals_text.splitlines().count('CREATE ROLE aos_app;')==1
    globals_text='\n'.join(x for x in globals_text.splitlines() if x!='CREATE ROLE aos_app;')+'\n'
    record('volume-create-intent.json',{'name':NAME,'sourceVolumeReused':False})
    docker('volume','create','--label','aos.task='+NAME,NAME,capture_output=True)
    record('clone-create-intent.json',{'name':NAME,'volume':NAME,'memoryBytes':536870912,'network':'none','originalBootstrap':'aos_app'})
    docker('run','-d','--name',NAME,'--network','none','--memory','512m','--memory-swap','512m','--mount','type=volume,src='+NAME+',dst=/var/lib/postgresql/data','-e','POSTGRES_USER=aos_app','-e','POSTGRES_HOST_AUTH_METHOD=trust',IMAGE,'-c','shared_buffers=16MB','-c','maintenance_work_mem=8MB','-c','work_mem=1MB','-c','max_parallel_workers_per_gather=0','-c','max_parallel_maintenance_workers=0','-c','max_connections=20',capture_output=True)
    for _ in range(30):
        r=subprocess.run(['docker','--context',CONTEXT,'exec',NAME,'pg_isready','-U','aos_app'],capture_output=True,timeout=5)
        if r.returncode==0:break
        time.sleep(1)
    else:raise RuntimeError('clone readiness failed; reconcile only')
    clone=json.loads(docker('inspect',NAME,text=True,capture_output=True).stdout)[0]
    assert clone['HostConfig']['NetworkMode']=='none' and not clone['HostConfig']['PortBindings'] and clone['Image']==IMAGE
    assert len(clone['Mounts'])==1 and clone['Mounts'][0]['Name']==NAME
    record('globals-intent.json',{'container':clone['Id'],'skipExactExistingBootstrapCreate':1})
    sql(NAME,'postgres',globals_text)
    docker('exec',NAME,'createdb','-U','aos_app','-O','aos_app',DB,capture_output=True)
    record('restore-intent.json',{'container':clone['Id'],'database':DB,'singleTransaction':True})
    try:docker('exec','-i',NAME,'pg_restore','--single-transaction','--exit-on-error','-U','aos_app','-d',DB,input=(private/'current.dump').read_bytes(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        record('restore-failure.json',{'exitCode':e.returncode,'stderr':e.stderr.decode(errors='replace'),'noReplay':True});raise
    restored=fingerprint(NAME,DB);restored_meta=metadata(NAME,DB)
    record('restore-comparison.json',{'tableEquality':restored==before,'metadataEquality':restored_meta==meta,'metadata':restored_meta})
    assert restored==before and restored_meta==meta,'full restore mismatch: do not rebind'
    spec=importlib.util.spec_from_file_location('rebind',ROOT/'.evidence/qyh-host-oid-full-restore-rehearsal-20261013/rehearse.py');R=importlib.util.module_from_spec(spec);spec.loader.exec_module(R)
    R.OUT=OUT;R.CLONE=NAME;R.ADMIN='aos_app';R.clone_fingerprint=lambda reader:fingerprint(NAME,DB)
    class Reader:
        def source_fingerprint(self):return fingerprint(SOURCE,'aos_meta_head')
    R.verify_rebind(Reader(),before,clone)
    assert metadata(SOURCE,'aos_meta_head')==meta
    record('source-after.json',{'source650Unchanged':True,'sourceMetadataUnchanged':True,'currentDatabaseWrites':False,'hostStarted':False,'eightWorkbenchesAccepted':False})

if __name__=='__main__':main()
