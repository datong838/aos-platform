import hashlib,importlib.util,json,os,shutil,subprocess,sys,time
from pathlib import Path
R=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('tools',R.parent/'qyh-org-name-maintenance-20261011'/'prepare.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
m.R=R;m.DB='aos_meta_head'
SOURCE='aos-qyh-history-restore-20261011';TARGET='aos-qyh-history159-prepared-20261011';VOLUME='aos-qyh-history159-prepared-data-20261011'
if (R/'intent.json').exists():raise RuntimeError('Existing intent; readonly reconcile only, no automatic replay')
identity=json.loads(m.psql(SOURCE,m.DB,"BEGIN READ ONLY; SELECT json_build_object('cluster',(SELECT system_identifier::text FROM pg_control_system()),'version',(SELECT version_num FROM alembic_version),'otherSessions',(SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid())); COMMIT;"))
assert identity=={'cluster':'7695294217975042088','version':'a0v_159','otherSessions':0}
oldsource=m.fingerprint(m.SOURCE);before=m.fingerprint(SOURCE)
assert oldsource==json.loads((R.parent/'qyh-historical-full-restore-20261011'/'source-before.json').read_text())
m.record('intent.json',{'source':SOURCE,'identity':identity,'target':TARGET,'volume':VOLUME,'image':m.IMAGE,'formalSwitch':False,'sourceWrites':False})
m.record('source159-before.json',before)
private=R/'private';private.mkdir(mode=0o700);os.chmod(private,0o700)
for name,args in [('history159.dump',['pg_dump','-U','aos_app','-d',m.DB,'-Fc']),('globals.sql',['pg_dumpall','-U','aos_app','--globals-only','--no-role-passwords'])]:
 with (private/name).open('xb') as out:
  os.chmod(private/name,0o600);p=subprocess.run(['docker','--context',m.CTX,'exec',SOURCE]+args,stdout=out,stderr=subprocess.PIPE,timeout=180)
  assert p.returncode==0,'Backup failed'
shutil.copyfile(private/'history159.dump',private/'history159.second.dump');os.chmod(private/'history159.second.dump',0o600)
files={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in private.iterdir()}
assert files['history159.dump']==files['history159.second.dump'];m.record('backup-manifest.json',{'files':files,'secondIsChecksumCopy':True,'rolePasswordsIncluded':False})
for command in [('inspect',TARGET),('volume','inspect',VOLUME)]:
 assert subprocess.run(['docker','--context',m.CTX]+list(command),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0,'Target exists; reconcile only'
m.record('create-intent.json',{'target':TARGET,'volume':VOLUME,'network':'none','ports':[],'sourceVolumesAttached':False})
m.run(['docker','--context',m.CTX,'volume','create','--label','aos.task=qyh-durable-restoration-preparation-20261011',VOLUME])
cid=m.run(['docker','--context',m.CTX,'run','--detach','--name',TARGET,'--network','none','--mount','type=volume,source='+VOLUME+',target=/var/lib/postgresql/data','-e','POSTGRES_HOST_AUTH_METHOD=trust','-e','POSTGRES_USER=aos_app',m.IMAGE]).decode().strip();m.record('created.json',{'containerId':cid})
for _ in range(30):
 if subprocess.run(['docker','--context',m.CTX,'exec',TARGET,'pg_isready','-U','aos_app'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:break
 time.sleep(.5)
assert m.psql(TARGET,'postgres',"BEGIN READ ONLY; SELECT oid FROM pg_roles WHERE rolname='aos_app'; COMMIT;")=='10'
raw=(private/'globals.sql').read_bytes();assert raw.count(b'CREATE ROLE aos_app;')==1
p=subprocess.run(['docker','--context',m.CTX,'exec','-i',TARGET,'psql','-X','-v','ON_ERROR_STOP=1','-U','aos_app','-d','postgres'],input=raw.replace(b'CREATE ROLE aos_app;',b'-- bootstrap aos_app OID10 already exists',1),capture_output=True,timeout=60)
(private/'globals-restore.log').write_bytes(p.stdout+p.stderr);os.chmod(private/'globals-restore.log',0o600);assert p.returncode==0
m.psql(TARGET,'postgres','CREATE DATABASE '+m.DB+' OWNER aos_app;')
m.run(['docker','--context',m.CTX,'cp',str(private/'history159.dump'),TARGET+':/tmp/history159.dump'])
m.record('restore-intent.json',{'targetId':cid,'dumpSha256':files['history159.dump']['sha256']})
p=subprocess.run(['docker','--context',m.CTX,'exec',TARGET,'pg_restore','--exit-on-error','-U','aos_app','-d',m.DB,'/tmp/history159.dump'],capture_output=True,timeout=180)
(private/'restore.log').write_bytes(p.stdout+p.stderr);os.chmod(private/'restore.log',0o600);m.record('restore-terminal.json',{'exit':p.returncode});assert p.returncode==0,'Restore failed; retained, no retry'
restored=m.fingerprint(TARGET);m.record('restored159.json',restored);assert restored==before
assert m.fingerprint(SOURCE)==before and m.fingerprint(m.SOURCE)==oldsource
x=json.loads(m.run(['docker','--context',m.CTX,'inspect',TARGET]))[0];assert x['HostConfig']['NetworkMode']=='none' and not x['HostConfig']['PortBindings'] and len(x['Mounts'])==1 and x['Mounts'][0]['Name']==VOLUME
final=json.loads(m.psql(TARGET,m.DB,"BEGIN READ ONLY; SELECT json_build_object('cluster',(SELECT system_identifier::text FROM pg_control_system()),'version',(SELECT version_num FROM alembic_version)); COMMIT;"));assert final['version']=='a0v_159' and final['cluster'] not in ('7683855731447750695','7695294217975042088')
m.record('result.json',{'outcome':'DURABLE_ISOLATED_HISTORY159_FULL_DATA_RESTORE_VERIFIED','tables':len(before),'targetId':cid,'volume':VOLUME,'identity':final,'source159Unchanged':True,'original092Unchanged':True,'rolesAclCatalogFinalReviewPending':True,'formalSwitch':False,'runtimeEnabled':False})
print(json.dumps({'outcome':'DURABLE_ISOLATED_HISTORY159_FULL_DATA_RESTORE_VERIFIED','tables':len(before),'identity':final}))
