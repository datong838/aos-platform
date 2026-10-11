import importlib.util,sys,subprocess,json,hashlib
from pathlib import Path
R=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('qyh_prepare',R/'prepare.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
# Reconcile exact existing target and partial globals result. Do not recreate it.
created=json.loads((R/'target-created.json').read_text())
identity=json.loads(m.run(['docker','--context',m.CTX,'inspect','--format','{"id":{{json .Id}},"image":{{json .Image}},"network":{{json .HostConfig.NetworkMode}},"ports":{{json .HostConfig.PortBindings}}}',m.TARGET]))
assert identity['id']==created['id'] and identity['image']==m.IMAGE and identity['network']=='none' and not identity['ports']
query="BEGIN READ ONLY; SELECT count(*) FROM pg_auth_members x JOIN pg_roles r ON r.oid=x.roleid WHERE r.rolname LIKE 'aos_%'; COMMIT;"
assert m.psql(m.TARGET,'postgres',query,m.ADMIN)=='0'
assert m.psql(m.TARGET,'postgres',"BEGIN READ ONLY; SELECT count(*) FROM pg_database WHERE datname='"+m.DB+"'; COMMIT;",m.ADMIN)=='0'
raw=(m.PRIVATE/'globals.sql').read_bytes();pos=raw.index(b'\nGRANT ');suffix=raw[pos:]
m.record('grantor-reconciliation.json',{'previousError':'grantor aos_app requires original granting role','target':identity,'existingSourceMemberships':0,'restoreDatabaseExists':False,'unexecutedSuffixSha256':hashlib.sha256(suffix).hexdigest(),'executor':'aos_app','sourceWrites':False})
result=subprocess.run(['docker','--context',m.CTX,'exec','-i',m.TARGET,'psql','-X','-v','ON_ERROR_STOP=1','-U','aos_app','-d','postgres'],input=suffix,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60)
(m.PRIVATE/'globals-grantor-resume.log').write_bytes(result.stdout+result.stderr)
assert result.returncode==0,'Exact grant suffix failed; reconcile'
m.psql(m.TARGET,'postgres','CREATE DATABASE '+m.DB+' OWNER aos_app;',m.ADMIN)
result=subprocess.run(['docker','--context',m.CTX,'exec',m.TARGET,'pg_restore','--exit-on-error','-U','aos_app','-d',m.DB,'/tmp/current.dump'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180)
(m.PRIVATE/'database-restore.log').write_bytes(result.stdout+result.stderr)
assert result.returncode==0,'Full restore failed; no partial-table fallback'
restored=m.fingerprint(m.TARGET,'aos_app');m.record('restored-fingerprint.json',restored)
original=json.loads((R/'source-fingerprint-before.json').read_text())
assert restored==original
m.record('restore-result.json',{'outcome':'FULL_DATA_RESTORE_FINGERPRINT_EQUAL','tables':len(original),'target':identity,'sourceWrites':False,'fullCatalogACLComparisonPending':True,'rolePasswordsRestored':False})
print(json.dumps({'outcome':'FULL_DATA_RESTORE_FINGERPRINT_EQUAL','tables':len(original)}))
