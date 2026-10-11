import importlib.util,sys,subprocess,json,time,hashlib,os
from pathlib import Path
R=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('qyh_prepare',R/'prepare.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
TARGET='aos-qyh-name-rehearsal-20261011-r3'
if (R/'r3-created.json').exists():raise RuntimeError('Reconcile existing r3 target; do not replay')
# The original grantor is the initdb bootstrap OID10. Preserve that role identity.
assert m.psql(m.SOURCE,m.DB,"BEGIN READ ONLY; SELECT oid FROM pg_roles WHERE rolname='aos_app'; COMMIT;")=='10'
raw=(m.PRIVATE/'globals.sql').read_bytes();exact=b'CREATE ROLE aos_app;'
assert raw.count(exact)==1
restore_globals=raw.replace(exact,b'-- aos_app already exists as the matching initdb bootstrap role.',1)
m.record('r3-intent.json',{'target':TARGET,'bootstrapRole':'aos_app','bootstrapOid':10,'sourceWrites':False,'originalGlobalsHash':hashlib.sha256(raw).hexdigest(),'adaptedGlobalsHash':hashlib.sha256(restore_globals).hexdigest(),'onlyAdaptation':'skip one exact CREATE ROLE for already matching initdb role; retain ALTER, settings and all original grantors','earlierTargetsRetained':True})
existing=subprocess.run(['docker','--context',m.CTX,'inspect',TARGET],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
assert not existing
cid=m.run(['docker','--context',m.CTX,'run','--detach','--name',TARGET,'--network','none','--tmpfs','/var/lib/postgresql/data:rw,nosuid,size=512m','-e','POSTGRES_HOST_AUTH_METHOD=trust','-e','POSTGRES_USER=aos_app',m.IMAGE]).decode().strip()
m.record('r3-created.json',{'id':cid,'name':TARGET})
for i in range(30):
 if subprocess.run(['docker','--context',m.CTX,'exec',TARGET,'pg_isready','-U','aos_app'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:break
 time.sleep(.5)
assert m.psql(TARGET,'postgres',"BEGIN READ ONLY; SELECT oid FROM pg_roles WHERE rolname='aos_app'; COMMIT;")=='10'
result=subprocess.run(['docker','--context',m.CTX,'exec','-i',TARGET,'psql','-X','-v','ON_ERROR_STOP=1','-U','aos_app','-d','postgres'],input=restore_globals,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60)
(m.PRIVATE/'r3-globals-restore.log').write_bytes(result.stdout+result.stderr);assert result.returncode==0,'Globals restoration failed'
m.psql(TARGET,'postgres','CREATE DATABASE '+m.DB+' OWNER aos_app;')
m.run(['docker','--context',m.CTX,'cp',str(m.PRIVATE/'current.dump'),TARGET+':/tmp/current.dump'])
result=subprocess.run(['docker','--context',m.CTX,'exec',TARGET,'pg_restore','--exit-on-error','-U','aos_app','-d',m.DB,'/tmp/current.dump'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180)
(m.PRIVATE/'r3-database-restore.log').write_bytes(result.stdout+result.stderr);assert result.returncode==0,'Full restore failed; preserve result'
restored=m.fingerprint(TARGET);m.record('r3-restored-fingerprint.json',restored)
source=json.loads((R/'source-fingerprint-before.json').read_text());assert source==restored
m.record('r3-restore-result.json',{'outcome':'FULL_DATA_RESTORE_FINGERPRINT_EQUAL','tables':len(source),'sourceWrites':False,'target':TARGET,'bootstrapRoleOid':10,'fullCatalogComparisonPending':True})
print(json.dumps({'outcome':'FULL_DATA_RESTORE_FINGERPRINT_EQUAL','tables':len(source),'sourceWrites':False}))
