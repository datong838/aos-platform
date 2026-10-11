import subprocess,json,hashlib,os,shutil,time
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parent
PRIVATE=R/'private'
CTX='colima-aos-extension';SOURCE='aos-a0v-recovery-pg';DB='aos_current_preview_20260927'
IMAGE='sha256:7e7dbab8d3b431a20793a6d99cb5a6bc84e44914309917f1bf5589a7568cdefd'
TARGET='aos-qyh-name-rehearsal-20261011';ADMIN='qyh_rehearsal_bootstrap'
def run(args,**kw):return subprocess.run(args,check=True,capture_output=True,timeout=180,**kw).stdout

def psql(container,db,sql,user='aos_app'):
 raw=run(['docker','--context',CTX,'exec','-i',container,'psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U',user,'-d',db],input=sql.encode())
 return raw.decode().strip()
def record(name,value):
 (R/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def fingerprint(container,user='aos_app'):
 tables=json.loads(psql(container,DB,"BEGIN READ ONLY; SELECT coalesce(json_agg(json_build_object('schema',n.nspname,'table',c.relname) ORDER BY n.nspname,c.relname),'[]') FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='r' AND n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%'; COMMIT;",user))
 quote=lambda s:'"'+s.replace('"','""')+'"'
 literal=lambda s:"'"+s.replace("'","''")+"'"
 statements=['BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;']
 for t in tables:
  table=t['schema']+'.'+t['table']
  statements.append("SELECT json_build_object('table',"+literal(table)+",'rows',count(*),'hash',md5(coalesce(string_agg(md5(to_jsonb(t)::text),'' ORDER BY md5(to_jsonb(t)::text)),''))) FROM ONLY "+quote(t['schema'])+'.'+quote(t['table'])+' t;')
 statements.append('COMMIT;')
 return [json.loads(line) for line in psql(container,DB,'\n'.join(statements),user).splitlines()]
if __name__=='__main__':
 if (R/'backup-manifest.json').exists():raise RuntimeError('Prior attempt exists; reconcile instead of replay')
 record('intent.json',{'at':datetime.now(timezone.utc).isoformat(),'source':SOURCE,'database':DB,'target':TARGET,'sourceWrites':False,'targetNetwork':'none','phase':'BACKUP_BEFORE_ISOLATED_CREATE'})
 source=json.loads(run(['docker','--context',CTX,'inspect','--format','{"Image":{{json .Image}},"Mounts":{{json .Mounts}}}',SOURCE]))
 assert source['Image']==IMAGE
 assert any(x.get('Name')=='aos-a0v-recovery-pg-data' and x['Destination']=='/var/lib/postgresql/data' for x in source['Mounts'])
 state=json.loads(psql(SOURCE,DB,"BEGIN READ ONLY; SELECT json_build_object('cluster',(SELECT system_identifier::text FROM pg_control_system()),'migration',(SELECT version_num FROM alembic_version),'zero',(SELECT count(*) FROM extension_runtime_binding)+(SELECT count(*) FROM extension_runtime_operation)+(SELECT count(*) FROM extension_runtime_host_assignment)+(SELECT count(*) FROM extension_runtime_host_identity),'name',(SELECT name FROM meta_org WHERE id='org-org')); COMMIT;"))
 assert state=={'cluster':'7683855731447750695','migration':'a0v_159','zero':0,'name':'org-org'}
 before=fingerprint(SOURCE);record('source-fingerprint-before.json',before)
 for filename,args in [('current.dump',['pg_dump','-U','aos_app','-d',DB,'-Fc']),('globals.sql',['pg_dumpall','-U','aos_app','--globals-only','--no-role-passwords'])]:
  path=PRIVATE/filename
  with path.open('xb') as out:
   os.chmod(path,0o600)
   result=subprocess.run(['docker','--context',CTX,'exec',SOURCE]+args,stdout=out,stderr=subprocess.PIPE,timeout=180)
   if result.returncode:raise RuntimeError('Backup failed '+result.stderr.decode()[:500])
 shutil.copyfile(PRIVATE/'current.dump',PRIVATE/'current.second.dump');os.chmod(PRIVATE/'current.second.dump',0o600)
 manifest={f:{'bytes':(PRIVATE/f).stat().st_size,'sha256':hashlib.sha256((PRIVATE/f).read_bytes()).hexdigest()} for f in ['current.dump','current.second.dump','globals.sql']}
 assert manifest['current.dump']==manifest['current.second.dump']
 record('backup-manifest.json',{'source':state,'files':manifest,'rolesPasswordIncluded':False})
 after=fingerprint(SOURCE);record('source-fingerprint-after-backup.json',after);assert before==after
 # Target creation and restoration are isolated effects, never production maintenance.
 exists=subprocess.run(['docker','--context',CTX,'inspect',TARGET],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
 if exists:raise RuntimeError('Target already exists; reconcile')
 record('target-intent.json',{'target':TARGET,'image':IMAGE,'network':'none','ports':[],'sourceVolumeAttached':False})
 cid=run(['docker','--context',CTX,'run','--detach','--name',TARGET,'--network','none','--tmpfs','/var/lib/postgresql/data:rw,nosuid,size=512m','-e','POSTGRES_HOST_AUTH_METHOD=trust','-e','POSTGRES_USER='+ADMIN,IMAGE]).decode().strip()
 record('target-created.json',{'id':cid,'name':TARGET})
 for i in range(30):
  ready=subprocess.run(['docker','--context',CTX,'exec',TARGET,'pg_isready','-U',ADMIN],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
  if ready:break
  time.sleep(0.5)
 if not ready:raise RuntimeError('Target not ready; reconcile existing target')
 run(['docker','--context',CTX,'cp',str(PRIVATE/'current.dump'),TARGET+':/tmp/current.dump'])
 globals_sql=(PRIVATE/'globals.sql').read_bytes()
 # Restore roles before owned database objects; target bootstrap role is independent.
 result=subprocess.run(['docker','--context',CTX,'exec','-i',TARGET,'psql','-X','-v','ON_ERROR_STOP=1','-U',ADMIN,'-d','postgres'],input=globals_sql,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60)
 (PRIVATE/'globals-restore.log').write_bytes(result.stdout+result.stderr)
 if result.returncode:raise RuntimeError('Globals restore failed; inspect private log')
 psql(TARGET,'postgres','CREATE DATABASE '+DB+' OWNER aos_app;',ADMIN)
 result=subprocess.run(['docker','--context',CTX,'exec',TARGET,'pg_restore','--exit-on-error','-U',ADMIN,'-d',DB,'/tmp/current.dump'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180)
 (PRIVATE/'database-restore.log').write_bytes(result.stdout+result.stderr)
 if result.returncode:raise RuntimeError('Complete database restore failed; do not downgrade to partial restore')
 restored=fingerprint(TARGET,ADMIN);record('restored-fingerprint.json',restored);assert before==restored
 record('restore-result.json',{'outcome':'FULL_DATA_RESTORE_FINGERPRINT_EQUAL','tables':len(before),'network':'none','ports':[],'sourceWrites':False,'rolePasswordRestoreProven':False,'fullCatalogACLComparisonPending':True})
 print(json.dumps({'outcome':'FULL_DATA_RESTORE_FINGERPRINT_EQUAL','tables':len(before),'sourceWrites':False}))
