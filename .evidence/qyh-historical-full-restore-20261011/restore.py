import hashlib,importlib.util,json,os,shutil,subprocess,sys,time
from pathlib import Path
R=Path(__file__).resolve().parent
OLD=R.parent/'qyh-org-name-maintenance-20261011'/'prepare.py'
spec=importlib.util.spec_from_file_location('original_restore_helper',OLD)
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
m.R=R;m.PRIVATE=R/'private';m.DB='aos_meta_head'
TARGET='aos-qyh-history-restore-20261011'
if (R/'intent.json').exists():raise RuntimeError('Existing attempt: reconcile target and backup before any retry')
m.PRIVATE.mkdir(mode=0o700);os.chmod(m.PRIVATE,0o700)
identity=json.loads(m.psql(m.SOURCE,m.DB,"BEGIN READ ONLY; SELECT json_build_object('cluster',(SELECT system_identifier::text FROM pg_control_system()),'migration',(SELECT version_num FROM alembic_version),'bootstrapOid',(SELECT oid FROM pg_roles WHERE rolname='aos_app'),'otherSessions',(SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid())); COMMIT;"))
assert identity=={'cluster':'7683855731447750695','migration':'a0v_092','bootstrapOid':'10','otherSessions':0}
source=json.loads(m.run(['docker','--context',m.CTX,'inspect','--format','{"Image":{{json .Image}},"Mounts":{{json .Mounts}}}',m.SOURCE]))
assert source['Image']==m.IMAGE
assert any(x.get('Name')=='aos-a0v-recovery-pg-data' and x['Destination']=='/var/lib/postgresql/data' for x in source['Mounts'])
m.record('intent.json',{'source':identity,'database':m.DB,'target':TARGET,'helperSha256':hashlib.sha256(OLD.read_bytes()).hexdigest(),'sourceWrites':False,'network':'none'})
before=m.fingerprint(m.SOURCE);m.record('source-before.json',before)
for name,args in [('history.dump',['pg_dump','-U','aos_app','-d',m.DB,'-Fc']),('globals.sql',['pg_dumpall','-U','aos_app','--globals-only','--no-role-passwords'])]:
    with (m.PRIVATE/name).open('xb') as out:
        os.chmod(m.PRIVATE/name,0o600)
        result=subprocess.run(['docker','--context',m.CTX,'exec',m.SOURCE]+args,stdout=out,stderr=subprocess.PIPE,timeout=180)
        if result.returncode:raise RuntimeError('Backup failed; source unchanged')
shutil.copyfile(m.PRIVATE/'history.dump',m.PRIVATE/'history.second.dump');os.chmod(m.PRIVATE/'history.second.dump',0o600)
files={name:{'bytes':(m.PRIVATE/name).stat().st_size,'sha256':hashlib.sha256((m.PRIVATE/name).read_bytes()).hexdigest()} for name in ['history.dump','history.second.dump','globals.sql']}
assert files['history.dump']==files['history.second.dump']
m.record('backup-manifest.json',{'files':files,'secondIsCopy':True,'rolePasswordsIncluded':False})
assert m.fingerprint(m.SOURCE)==before
exists=subprocess.run(['docker','--context',m.CTX,'inspect',TARGET],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
assert not exists
m.record('create-intent.json',{'target':TARGET,'image':m.IMAGE,'ports':[],'sourceVolumeAttached':False,'data':'independent tmpfs1G'})
cid=m.run(['docker','--context',m.CTX,'run','--detach','--name',TARGET,'--network','none','--tmpfs','/var/lib/postgresql/data:rw,nosuid,size=1g','-e','POSTGRES_HOST_AUTH_METHOD=trust','-e','POSTGRES_USER=aos_app',m.IMAGE]).decode().strip()
m.record('created.json',{'containerId':cid,'target':TARGET})
for _ in range(30):
    if subprocess.run(['docker','--context',m.CTX,'exec',TARGET,'pg_isready','-U','aos_app'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:break
    time.sleep(.5)
assert m.psql(TARGET,'postgres',"BEGIN READ ONLY; SELECT oid FROM pg_roles WHERE rolname='aos_app'; COMMIT;")=='10'
raw=(m.PRIVATE/'globals.sql').read_bytes();assert raw.count(b'CREATE ROLE aos_app;')==1
adapted=raw.replace(b'CREATE ROLE aos_app;',b'-- matching original bootstrap aos_app OID10 already exists',1)
result=subprocess.run(['docker','--context',m.CTX,'exec','-i',TARGET,'psql','-X','-v','ON_ERROR_STOP=1','-U','aos_app','-d','postgres'],input=adapted,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60)
(m.PRIVATE/'globals-restore.log').write_bytes(result.stdout+result.stderr);os.chmod(m.PRIVATE/'globals-restore.log',0o600)
assert result.returncode==0,'Globals restore failed; retained'
m.psql(TARGET,'postgres','CREATE DATABASE '+m.DB+' OWNER aos_app;')
m.run(['docker','--context',m.CTX,'cp',str(m.PRIVATE/'history.dump'),TARGET+':/tmp/history.dump'])
result=subprocess.run(['docker','--context',m.CTX,'exec',TARGET,'pg_restore','--exit-on-error','-U','aos_app','-d',m.DB,'/tmp/history.dump'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180)
(m.PRIVATE/'database-restore.log').write_bytes(result.stdout+result.stderr);os.chmod(m.PRIVATE/'database-restore.log',0o600)
assert result.returncode==0,'Full restore failed; no partial acceptance'
restored=m.fingerprint(TARGET);m.record('restored.json',restored);assert restored==before
after=m.fingerprint(m.SOURCE);m.record('source-after.json',after);assert after==before
m.record('result.json',{'outcome':'FULL_HISTORICAL_DATA_RESTORE_FINGERPRINT_EQUAL','tables':len(before),'target':TARGET,'sourceWrites':False,'schemaRolesAclFullReviewPending':True,'migrationPending':True})
print(json.dumps({'outcome':'FULL_HISTORICAL_DATA_RESTORE_FINGERPRINT_EQUAL','tables':len(before),'sourceWrites':False}))
